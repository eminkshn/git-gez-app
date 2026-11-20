# Sonraki adımlar (proje kapsamı dışında)

Ders projesi şu an **tek kullanıcılı, dizüstünde çalışan bir web arayüzü** (Gradio). Hava durumu ve geçmiş trafik
eklendi (bkz. `PLAN_TRAFIK_HAVA.md`). Aşağıdakiler **gerçek bir ürün** için gerekenler; sunumda "Limits / Next steps"
slaytında ve raporun *Limitations* bölümünde kısaca geçer.

| # | Adım | Neden | Ne gerekir | Algoritmaya etkisi |
|---|---|---|---|---|
| 1 | **Canlı veri** (anlık trafik, araç konumu, sefer iptali) | Şu an trafik *geçmiş ortalaması*, otobüs konumu yok | İBB/İETT anlık servisleri (API anahtarı, kullanım izni), sürekli çalışan bir sunucu | Graf her birkaç dakikada güncellenir; tüm grafı yeniden kurmak yerine sadece değişen kenarlar. Saat çizelgesi (timetable) tabanlı arama (ör. RAPTOR / CSA) daha uygun olur |
| 2 | **Backend'li mobil uygulama** | Telefonda hızlı açılış, 1,3 GB belleği telefona yüklememek | Sunucuda API (ör. FastAPI) + mobil istemci (Flutter / React Native). Graf sunucuda bir kez belleğe alınır | Algoritmalar aynı kalır, sadece sunucuya taşınır; önbellek tüm kullanıcılar arasında paylaşılır |
| 3 | **GPS takibi** | "Şu an neredeyim, inmem gereken durak geldi mi?" | Telefon konum izni, arka planda konum, pil tüketimi | Rotadan sapınca o noktadan yeniden arama (A* burada hızlı olduğu için işe yarar) |
| 4 | **Mağaza yayını** (Google Play / App Store) | Herkesin kurabilmesi | Geliştirici hesapları, gizlilik politikası (KVKK), veri lisanslarına uygunluk (İBB açık veri, ODbL), mağaza incelemesi | Yok |
| 5 | **Çok kullanıcı** | Aynı anda birçok kişi | Ölçeklenen sunucu, oturum/kimlik, istek sınırlama, izleme | Sorgu başına O((V+E) log V) maliyet; sık sorulan rotalar önbelleğe; gerekirse ön hesaplama (Contraction Hierarchies vb.) |

Ek fikirler: kullanıcı geri bildirimi ("bu yokuş çok dik"), asansör/yürüyen merdiven arıza verisi (engelli profili için),
erişilebilir durak bilgisinin doğrulanması, çok günlü gezi planı.

## Hugging Face Spaces / kalıcı bağlantı ne işe yarar?
`gradio.live` bağlantısı (Colab ya da `share=True`) **72 saat** yaşar ve dizüstü/Colab kapanınca ölür.
Hugging Face Spaces aynı Gradio uygulamasını **ücretsiz bir sunucuda** çalıştırır ve sabit bir adres verir
(ör. `https://huggingface.co/spaces/<kullanici>/gitgez`).

- Hoca ve ekip arkadaşları istedikleri zaman telefondan/bilgisayardan deneyebilir; sunumdan sonra da açık kalır.
- Rapora ve slayda tek bir bağlantı (ya da QR kod) konabilir.
- Space **gizli (private)** yapılabilir; sadece davet edilenler görür.
- Sınırlar: ücretsiz CPU (2 vCPU, 16 GB RAM) bu uygulamaya yeter ama ilk açılış ~1 dk sürer; 48 saat kullanılmazsa uyur,
  ilk ziyaretçide tekrar uyanır. Veri zip'i (55 MB) Space'e yüklenmeli.
- **Ders için şart değil**: sunum dizüstünden yapılacak. Ancak "canlı demo bağlantısı" olarak güzel bir artı.
