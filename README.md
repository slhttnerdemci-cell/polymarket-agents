# Polymarket paper masası

5 dakikalık kripto Up/Down piyasası için paper trading. Altı modül sinyal üretir. Orkestratör `al`, `sat` veya `bekle` der. Execution Engine emri o anki deftere yürür. Gerçek emir ve cüzdan yoktur.

## Çalıştırma

```bash
pip install -r requirements.txt
python -m unittest tests.test_desk
streamlit run ui/dashboard.py
```

Arayüzde iki düğme vardır. `Tek tur bak` bir yoklama yapar ve kararı gösterir. `Bu pencereyi çalıştır` pencere kapanana kadar paper turunu sürdürür. Kararlar ekranda tur tur güncellenir.

Tek pencereyi terminalden çalıştırmak için:

```bash
python -m simulation.run_paper
```

Arayüzden değişen değerler kenar eşiği, tampon, ücret katsayısı, risk, tutma süresi ve sanal bankrolldur. BTC 5 dakikalık ücret katsayısı 0,05'tir. Maliyet `pay × katsayı × fiyat × (1 − fiyat)` ile her iki bacağa uygulanır.

Kapanan kâr, dolan payın giriş ve çıkış fiyatından ücret düşülerek yazılır. Açık pozisyon bu sayıya girmez.
