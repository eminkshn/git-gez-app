"""Overture Maps (OSM tabanlı) yol segmentlerini İstanbul kutusu için indirir -> streets.parquet
Row-group istatistikleri (bbox) ile sadece İstanbul'a düşen parçalar okunur."""
import os, time
from concurrent.futures import ThreadPoolExecutor
import s3fs, pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc

REL = "2026-10-21.0"
W, S, E, N = 27.97, 40.76, 29.90, 41.50
COLS = ["id", "subtype", "class", "subclass", "connectors", "geometry", "bbox", "names", "level_rules", "road_flags"]
fs = s3fs.S3FileSystem(anon=True, client_kwargs={"region_name": "us-west-2"})
files = fs.ls(f"overturemaps-us-west-2/release/{REL}/theme=transportation/type=segment/")


def stats_of(md, rg, name):
    for c in range(md.num_columns):
        col = md.row_group(rg).column(c)
        if col.path_in_schema == name:
            s = col.statistics
            return (s.min, s.max) if s is not None and s.has_min_max else (None, None)
    return (None, None)


def work(path):
    out = []
    with fs.open(path, block_size=4 * 2**20) as fh:
        f = pq.ParquetFile(fh)
        md = f.metadata
        keep = []
        for rg in range(md.num_row_groups):
            xmin = stats_of(md, rg, "bbox.xmin"); xmax = stats_of(md, rg, "bbox.xmax")
            ymin = stats_of(md, rg, "bbox.ymin"); ymax = stats_of(md, rg, "bbox.ymax")
            if None in (xmin[0], xmax[1], ymin[0], ymax[1]):
                keep.append(rg); continue
            if xmin[0] < E and xmax[1] > W and ymin[0] < N and ymax[1] > S:
                keep.append(rg)
        for rg in keep:
            t = f.read_row_group(rg, columns=COLS)
            b = t.column("bbox")
            m = pc.and_(pc.and_(pc.less(pc.struct_field(b, "xmin"), E), pc.greater(pc.struct_field(b, "xmax"), W)),
                        pc.and_(pc.less(pc.struct_field(b, "ymin"), N), pc.greater(pc.struct_field(b, "ymax"), S)))
            m = pc.and_(m, pc.equal(t.column("subtype"), "road"))
            t = t.filter(m)
            if t.num_rows:
                t = t.append_column("name", pc.struct_field(t.column("names"), "primary")).drop_columns(["names", "bbox", "subtype"])
                out.append(t)
    return path, out


t0 = time.time()
tables = []
with ThreadPoolExecutor(16) as ex:
    for i, (p, out) in enumerate(ex.map(work, files)):
        n = sum(t.num_rows for t in out)
        if n:
            print(f"{os.path.basename(p)[:12]} -> {n} segment", flush=True)
        tables += out
tab = pa.concat_tables(tables, promote_options="permissive")
pq.write_table(tab, "streets.parquet", compression="zstd")
print("toplam", tab.num_rows, "segment", f"{time.time() - t0:.0f} sn")
