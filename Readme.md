# CBAM CO₂ Emissions Estimator for Imports

Vizualizează rapid emisiile estimate de CO₂ asociate importurilor, folosind date UN Comtrade și factori de emisii specifici pe țară/produs, direct din browser — interfață modernă, filtru multiplu, export, sortare și afișare tabelară cu DataTables.

---

## 🚀 Testare rapidă în Google Colab

**Pași de rulare:**
1. **Clonează repository-ul:**
    ```python
    !git clone https://github.com/pasatsanduadrian/ComTradeEmissions.git
    %cd ComTradeEmissions
    ```

2. **Instalează dependențele:**
    ```python
    !pip install -r requirements.txt
    ```

3. **Creează fișierul `.env` cu variabilele de mediu:**
    ```python
    with open('.env', 'w') as f:
        f.write(
            "COMTRADE_API_KEY=API KEY de copiat aici\n"
            "NGROK_TOKEN=API KEY de copiat aici\n"
            "EMISSIONS_FILE=/content/emissions.xlsx\n"
            "PORT=5099\n"
            "NGROK_HOSTNAME=XXXXX-guided-buck.ngrok-free.app\n"
        )
    ```

4. **Încarcă fișierul `emissions.xlsx` în workspace-ul Colab**  
   (Este necesar pentru rularea aplicației. Pentru acces la fișier, trimite un mesaj privat.)

5. **Pornește aplicația web:**
    ```python
    !python app.py
    ```
    - Vei vedea link-ul public generat de ngrok în output-ul notebook-ului.
    - Accesează link-ul pentru a folosi aplicația din browser (formulare moderne, filtru rapid, tabel cu sortare/export, temă dark).

---

## 💡 Notă despre fișierul `emissions.xlsx`

- Acest fișier conține factorii de emisii pe țară, codurile HS și lista țărilor reporter.
- Pentru acces la fișierul actualizat, **trimite mesaj privat** (PM).
- Structura așteptată:
  - Sheet1: Emissions Factors
  - Sheet2: HS Codes
  - Sheet3: Reporter Countries

---

## 🛠️ Rulare locală (Windows/Linux/Mac)

1. Clonează repo și instalează dependențele (`requirements.txt`).
2. Creează `.env` cu datele tale.
3. Pune fișierul `emissions.xlsx` în directorul specificat în `.env`.
4. Rulează aplicația cu:
    ```sh
    python app.py
    ```

---

