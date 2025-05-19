import os
import pandas as pd
import requests
from flask import Flask, request
from pyngrok import ngrok
from dotenv import load_dotenv
import threading

# ============ Config & ENV =================
load_dotenv()
EXCEL_FILE = os.environ.get("EMISSIONS_FILE", "emissions.xlsx")
COMTRADE_API_KEY = os.environ.get("COMTRADE_API_KEY")
NGROK_TOKEN = os.environ.get("NGROK_TOKEN")
NGROK_HOSTNAME = os.environ.get("NGROK_HOSTNAME", None)
PORT = int(os.environ.get("PORT", "5099"))

# ========== Load Data & Prepare UI =========
def load_emissions_data(path):
    df_emis = pd.read_excel(path, sheet_name="Sheet1")
    df_emis["Code"] = df_emis["Code"].astype(str).str.strip()
    df_emis["Description"] = df_emis["Description"].astype(str).str.strip()
    df_HS = pd.read_excel(path, sheet_name="Sheet2")
    df_HS["HS Code"] = df_HS["HS Code"].astype(str).str.strip()
    df_HS["Description"] = df_HS["Description"].astype(str).str.strip()
    df_country = pd.read_excel(path, sheet_name="Sheet3")
    df_country["Country"] = df_country["Country"].astype(str).str.strip()
    df_country["ID"] = df_country["ID"].astype(str).str.strip()
    return df_emis, df_HS, df_country

def build_dropdowns(df_HS, df_country):
    hs_options = "\n".join([
        f'<option value="{row["HS Code"]}|{row["Description"]}">{row["HS Code"]} - {row["Description"]}</option>'
        for _, row in df_HS.iterrows()
    ])
    reporter_options = "\n".join([
        f'<option value="{row["Country"]}|{row["ID"]}">{row["Country"]} | {row["ID"]}</option>'
        for _, row in df_country.iterrows()
    ])
    return hs_options, reporter_options

def build_emissions_dicts(df_emis):
    country_code_desc_to_emis = {}
    weighted_code_desc_to_emis = {}
    for _, row in df_emis.iterrows():
        country, code, desc = row["Country"], str(row["Code"]).strip(), str(row["Description"]).strip()
        d, i, t = row["Direct"], row["Indirect"], row["Total"]
        if country == "Weighted average":
            weighted_code_desc_to_emis[(code, desc)] = (d, i, t)
        else:
            country_code_desc_to_emis[(country, code, desc)] = (d, i, t)
    return country_code_desc_to_emis, weighted_code_desc_to_emis

country_name_mapping = {
    "USA": "United States", "USA and Puerto Rico (...1980)": "United States",
    "United States Minor Outlying Islands": "United States",
    "Dem. Rep. of Vietnam (...1974)": "Viet Nam",
    "Norway, excluding Svalbard and Jan Mayen": "Norway",
    "Peninsula Malaysia (...1963)": "Malaysia",
    "Serbia and Montenegro (...2005)": "Serbia",
    "Sikkim, Protectorate of India (...1974)": "India"
}
eu_countries = [
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia", "Denmark", "Estonia", "Finland", "France",
    "Germany", "Greece", "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands",
    "Poland", "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden"
]

# Load data at start
df_emis, df_HS, df_country = load_emissions_data(EXCEL_FILE)
hs_options, reporter_options = build_dropdowns(df_HS, df_country)
country_code_desc_to_emis, weighted_code_desc_to_emis = build_emissions_dicts(df_emis)

# ========== Flask App ==========
app = Flask(__name__)

HTML_FORM = f"""
<!DOCTYPE html>
<html>
<head>
    <title>CBAM CO₂ Emissions Estimator for Imports</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <style>
      body {{
          font-family: Arial, sans-serif;
          margin: 40px;
          background-color: #f8f9fa;
      }}
      .container {{
          background-color: #ffffff;
          padding: 30px;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      }}
      h1 {{
          margin-bottom: 10px;
      }}
      p.description {{
          font-size: 1.1em;
          margin-bottom: 30px;
      }}
      .header-img {{
          max-width: 100%;
          height: auto;
          margin-bottom: 20px;
      }}
    </style>
</head>
<body>
    <div class="container">
      <img src="https://oneclicklca.com/hubfs/Blog%20images/Decarbonization%20News/decarbonizationnews_infographics_cbam_how%20does%20CBAM%20work.webp" class="header-img" alt="CBAM Illustration"/>
      <h1>CBAM CO₂ Emissions Estimator for Imports</h1>
      <p class="description">
        With the CBAM framework increasingly shaping global trade for carbon-intensive goods, our application helps stakeholders quickly retrieve, analyze, and estimate the CO₂ emissions embedded in imports. By pairing UN Comtrade data with country- and commodity-specific emission factors, it offers a streamlined method to gauge potential CBAM obligations and support more sustainable trade practices.
      </p>
      <form method="POST" action="/compute">
          <div class="form-group">
              <label for="year">Enter Year (YYYY):</label>
              <input type="text" class="form-control" name="year" value="2021" required/>
          </div>
          <div class="form-group">
              <label for="reporter">Select Reporter Country (Country | ID):</label>
              <select name="reporter" class="form-control" required>
                  {reporter_options}
              </select>
          </div>
          <div class="form-group">
              <label for="flowCode">Flow Code (M=import, X=export):</label>
              <select name="flowCode" class="form-control" required>
                  <option value="M">Import</option>
                  <option value="X">Export</option>
              </select>
          </div>
          <div class="form-group">
              <label for="HSCodeDesc">Select HS Code + Description:</label>
              <select name="HSCodeDesc" class="form-control" required>
                  {hs_options}
              </select>
          </div>
          <button type="submit" class="btn btn-primary">Compute</button>
      </form>
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return HTML_FORM

@app.route("/compute", methods=["POST"])
def compute():
    year = request.form.get("year", "2021")
    reporter_combined = request.form.get("reporter", "")
    flowCode = request.form.get("flowCode", "M")
    hs_combined = request.form.get("HSCodeDesc", "")

    if "|" not in reporter_combined or "|" not in hs_combined:
        return "<h3>Error: Invalid input.</h3>"
    reporter_country, reporter_id = [s.strip() for s in reporter_combined.split("|", 1)]
    HSCode, HSDesc = [s.strip() for s in hs_combined.split("|", 1)]

    BASE_URL = "https://comtradeapi.un.org/data/v1/get/C/A/HS"
    params = {
        "reporterCode": reporter_id,
        "period": year,
        "flowCode": flowCode,
        "includeDesc": "true",
        "cmdCode": HSCode,
        "partner2Code": "0"
    }
    headers = {"Ocp-Apim-Subscription-Key": COMTRADE_API_KEY}
    resp = requests.get(BASE_URL, params=params, headers=headers)
    if resp.status_code != 200:
        return f"<h3>Error: {resp.status_code} => {resp.text}</h3>"

    json_data = resp.json()
    data_list = json_data.get("data", [])
    if not data_list:
        return "<h3>No data found for selection.</h3>"
    df_data = pd.DataFrame(data_list)

    # Filter and process
    for col in ("motDesc", "customsDesc"):
        if col in df_data.columns:
            df_data[col] = df_data[col].astype(str).str.strip()
    df_data = df_data[(df_data.get("motDesc", "") == "TOTAL MOT") & (df_data.get("customsDesc", "") == "TOTAL CPC")]
    df_data.drop_duplicates(inplace=True)
    if df_data.empty:
        return "<h3>No data after filter (TOTAL MOT/CPC).</h3>"

    columns_mapping = {
        "period": "Period", "flowDesc": "Trade Flow", "reporterDesc": "Reporter",
        "partnerDesc": "Partner", "partner2Desc": "2nd Partner", "cmdCode": "Commodity Code",
        "cmdDesc": "Commodity Desc", "cifvalue": "Trade Value (US$)", "netWgt": "Net Weight (kg)", "altQty": "Alternate Qty"
    }
    df_selected = df_data[list(columns_mapping.keys())].copy()
    df_selected.rename(columns=columns_mapping, inplace=True)
    for col in ["Trade Value (US$)", "Net Weight (kg)", "Alternate Qty"]:
        df_selected[col] = pd.to_numeric(df_selected[col], errors="coerce").fillna(0.0).round(2)
    df_selected.insert(0, "Year", year)
    df_selected["Net Weight (ton)"] = (df_selected["Net Weight (kg)"] / 1000.0).round(2)

    def calc_final_weight(row):
        if row["Net Weight (kg)"] == 0 and row["Alternate Qty"] != 0:
            return round(row["Alternate Qty"] / 1000.0, 2)
        return row["Net Weight (ton)"]
    df_selected["Final Weight (ton)"] = df_selected.apply(calc_final_weight, axis=1)
    all_second_world = (df_selected["2nd Partner"].nunique() == 1 and df_selected["2nd Partner"].unique()[0] == "World")

    def calc_emissions(row):
        trade_ctry = row["Partner"].strip() if all_second_world else row["2nd Partner"].strip()
        trade_ctry = country_name_mapping.get(trade_ctry, trade_ctry)
        key = (trade_ctry, HSCode, HSDesc)
        if key in country_code_desc_to_emis:
            d, i, t = country_code_desc_to_emis[key]
        elif trade_ctry in eu_countries and ("EU", HSCode, HSDesc) in country_code_desc_to_emis:
            d, i, t = country_code_desc_to_emis[("EU", HSCode, HSDesc)]
        else:
            d, i, t = weighted_code_desc_to_emis.get((HSCode, HSDesc), (0, 0, 0))
        final_weight = row["Final Weight (ton)"]
        co2_direct = d * final_weight
        co2_indirect = i * final_weight
        co2_total = t * final_weight
        return pd.Series([d, i, t, co2_direct, co2_indirect, co2_total],
            index=["directFactor", "indirectFactor", "totalFactor", "CO2_Direct", "CO2_Indirect", "CO2_Total"])

    df_emissions_calc = df_selected.apply(calc_emissions, axis=1)
    df_result = pd.concat([df_selected, df_emissions_calc], axis=1)
    final_columns = [
        "Year", "Period", "Trade Flow", "Reporter", "Partner", "2nd Partner",
        "Commodity Code", "Commodity Desc", "Trade Value (US$)", "Net Weight (kg)",
        "Net Weight (ton)", "Alternate Qty", "Final Weight (ton)",
        "directFactor", "indirectFactor", "totalFactor",
        "CO2_Direct", "CO2_Indirect", "CO2_Total"
    ]
    df_result = df_result[final_columns].copy()
    for col in ["CO2_Direct", "CO2_Indirect", "CO2_Total"]:
        df_result[col] = df_result[col].apply(lambda x: f"{x:.2f} ton CO₂")

    html_table = df_result.to_html(
        index=False, classes="table table-striped table-bordered", border=0
    )

    html_response = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>CBAM CO₂ Emissions Dashboard</title>
        <!-- Bootstrap 4 CSS -->
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
        <!-- DataTables CSS (Bootstrap 4) -->
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.4/css/dataTables.bootstrap4.min.css">
        <!-- DataTables Buttons extension CSS (Bootstrap 4) -->
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/2.3.6/css/buttons.bootstrap4.min.css">
        <!-- jQuery and DataTables JS -->
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.4/js/dataTables.bootstrap4.min.js"></script>
        <script src="https://cdn.datatables.net/buttons/2.3.6/js/dataTables.buttons.min.js"></script>
        <script src="https://cdn.datatables.net/buttons/2.3.6/js/buttons.bootstrap4.min.js"></script>
        <script src="https://cdn.datatables.net/buttons/2.3.6/js/buttons.colVis.min.js"></script>
        <style>
            body {{
                background-color: #1f1f1f;
                color: #fff;
                font-family: Arial, sans-serif;
                margin: 20px;
            }}
            h3 {{
                margin-bottom: 20px;
            }}
            .dashboard-container {{
                background-color: #2f2f2f;
                padding: 20px;
                border-radius: 8px;
            }}
            .dataTables_wrapper .dt-buttons {{
                float: left;
                margin-bottom: 10px;
            }}
            .dataTables_filter {{
                float: right;
            }}
            .table-responsive {{
                overflow-x: auto;
            }}
            table.dataTable thead th,
            table.dataTable tbody td {{
                color: #fff !important;
                background-color: #3a3a3a !important;
            }}
            table.table-striped tbody tr:nth-of-type(odd) td {{
                background-color: #353535 !important;
            }}
        </style>
    </head>
    <body>
        <div class="container-fluid dashboard-container">
            <h3>CBAM CO₂ Emissions Dashboard for year={year}, HSCode={HSCode} ({HSDesc}), Flow={flowCode}</h3>
            <div class="table-responsive">
                {html_table}
            </div>
        </div>
        <script>
          $(document).ready(function() {{
              $('table.table').DataTable({{
                  dom: 'Bfrtip',
                  buttons: [
                      {{
                          extend: 'colvis',
                          text: 'Hide/Show Columns'
                      }}
                  ],
                  paging: true,
                  searching: true,
                  ordering: true,
                  scrollX: true,
                  autoWidth: false
              }});
          }});
        </script>
    </body>
    </html>
    """
    return html_response

# ========== NGROK/FLASK RUNNER ==========
def start_ngrok(app, port):
    if NGROK_TOKEN:
        ngrok.set_auth_token(NGROK_TOKEN)
        try:
            public_url = ngrok.connect(port, hostname=NGROK_HOSTNAME) if NGROK_HOSTNAME else ngrok.connect(port)
            print(f"Public URL: {public_url.public_url}")
        except Exception as e:
            print("Error with static domain, fallback:", e)
            public_url = ngrok.connect(port)
            print(f"Public URL: {public_url.public_url}")
    else:
        print("Ngrok token missing; app available only locally.")
    app.run(port=port, debug=False)

if __name__ == "__main__":
    threading.Thread(target=lambda: start_ngrok(app, PORT)).start()
