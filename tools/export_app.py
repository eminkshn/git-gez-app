"""Defterden app.py üretir: kurulum, test ve analiz hücreleri hariç tüm kod."""
import sys, nbformat
src, out = sys.argv[1], sys.argv[2]
nb = nbformat.read(src, as_version=4)
skip = ("%pip", "def run_tests(", "def dijkstra_naive(", "def pairs_naive(", "G0 = yer_ara(")
parts = [c.source for c in nb.cells if c.cell_type == "code" and not any(k in c.source for k in skip)]
import os
ad = os.path.basename(src)
head = ('"""GitGez — İstanbul rota ve gezi planlayıcı, yerel arayüz.\n'
        f'Bu dosya {ad} defterinden otomatik üretilir (tools/export_app.py); düzenlemeleri deftere yapın.\n'
        'Kurulum : pip install -r requirements.txt  (gradio, numpy, scipy, requests ...)\n'
        'Veri    : gitgez_veri.zip (yokus-gezi/ klasöründe; açmayın)\n'
        'Çalıştır: python app.py  ->  http://127.0.0.1:7860\n"""\n'
        'import os\nos.chdir(os.path.dirname(os.path.abspath(__file__)))\n')
open(out, "w", encoding="utf-8").write(head + "\n\n# " + "-" * 70 + "\n\n".join([""] + parts) + "\n")
print("ok", len(parts), "hücre")
