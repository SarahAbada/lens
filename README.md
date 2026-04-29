
# Lens — What It Is and What Every Number Means
https://youtu.be/ExJLFCLqqps?si=ZGGaqGdLjOH2GlV-
Lens is a transparency tool that answers: "Where is public money going, how concentrated is it in a few vendors, and should we be worried?"
It pulls real federal grant data from the Government of Canada's open data API, loads it into a local PostgreSQL database, and gives you interactive analytics, AI-generated risk briefings, and cross-dataset entity lookups — all in a browser.

## The Sidebar (left panel)
### System Health Monitor
Three status indicators that tell you whether you're looking at real data or demo data:
Data Authenticity:
🟢 LIVE DATA — The dashboard is connected to the local PostgreSQL database and/or S3 mount. The numbers you see are from real government datasets (CRA charity filings, federal grants, Alberta procurement). This is what you want.
🟡 SCHEMA ONLY — The database tables exist but have no data in them yet. You're seeing the structure but not the content.
🔴 STUBBED DATA — No database, no S3, nothing. The dashboard falls back to a 42-row sample CSV we bundled for demo purposes. The numbers are fake.
LLM Provider:
🟣 COHERE ACTIVE — Cohere Command R+ is configured and ready to generate live AI analysis.
🔵 BEDROCK ACTIVE — Amazon Bedrock (Claude) is the active AI provider.
⚪ PLACEHOLDER — No AI provider configured. The "Generate" buttons still work but return a canned template instead of live AI output.
Filters
Department and Spend Category dropdowns filter the Overview tab's data. "All" means no filter. When you select "Engineering" for example, every number on the Overview tab recalculates to show only Engineering's vendors and spend.

### Tab 1: 📊 Overview
This is the core vendor concentration analysis. It answers: "If one of our big vendors disappeared tomorrow, how screwed are we?"
The Four KPI Cards
Total Spend — The sum of all contract dollar values in the current filter. If you're looking at "All" departments, this is the total across the entire dataset. The small number underneath is the count of individual contract line items.
HHI Score — The Herfindahl-Hirschman Index. This is a real economics metric used by the U.S. Department of Justice and the FTC to measure market concentration. Here's how it works:
Take each vendor's percentage share of total spend
Square each percentage
Add them all up
Example: If you have 4 vendors each with 25% share: 25² + 25² + 25² + 25² = 2,500. If one vendor has 100%: 100² = 10,000.
The scale:
Green (< 1,500): Competitive. Spend is spread across many vendors. Losing one wouldn't be catastrophic.
Yellow (1,500–2,500): Moderately concentrated. A few vendors dominate. Worth watching.
Red (> 2,500): Highly concentrated. One or two vendors hold most of the spend. High risk if they fail or raise prices.
Resilience Score — A 1-to-100 score we derived from HHI. The formula is 100 × (1 − HHI/10,000). It's the inverse of concentration — higher is better.
100 = perfectly diversified (impossible in practice, but the ideal)
50 = moderately concentrated
1 = single vendor monopoly
This exists because HHI is hard to intuit. "Resilience 92" is easier to grasp than "HHI 782."
Top-3 Concentration — What percentage of total spend goes to just the three biggest vendors. If this number is 80%, it means 80 cents of every dollar goes to three companies. The color coding:
Green (< 50%): Healthy spread
Yellow (50–70%): Getting concentrated
Red (> 70%): Dangerously top-heavy
Vendor Market Share Bar Chart
A horizontal bar chart showing each vendor's share of total spend (as a percentage). The red dashed line at 40% is a risk threshold — any vendor above that line holds a disproportionate share. Bars are color-coded: red if ≥ 40%, otherwise a rotating palette.
Hover over any bar to see the exact dollar amount and percentage.
Resilience Score Gauge
A speedometer-style gauge. The colored zones match the HHI thresholds:
Red zone (0–35): High risk
Yellow zone (35–60): Moderate risk
Green zone (60–100): Low risk
The "+X vs 50" delta shows how far above or below the midpoint you are.
Top 3 Vendors (right sidebar)
Mini progress bars showing the three biggest vendors by spend share. Red bar = ≥ 40% share, yellow = ≥ 25%, green = below 25%.
Department-Level HHI Overview (expandable)
A bar chart comparing HHI across all departments side by side. This answers: "Which departments have the worst vendor concentration?" The dashed lines at 1,500 and 2,500 show the moderate/high thresholds. The table on the right shows each department's total spend, vendor count, HHI, and resilience score.
AI Strategic Risk Briefing
Click the button and the configured LLM (Bedrock, Gemini, Cohere, or placeholder) analyzes the current filtered data and writes a 3-5 bullet point risk assessment. It sees the HHI, resilience score, top vendors, and their shares, then identifies the primary risk and recommends specific actions.
With Bedrock active, this is a live Claude call. With placeholder, it returns a realistic-looking template.
Scenario Simulator
Toggle "Force Diversification" and the dashboard simulates what would happen if you took 10% of the dominant vendors' budgets and redistributed it equally to the smaller vendors. It shows:
Original HHI → Simulated HHI (the delta shows how much concentration drops)
Original Resilience → Simulated Resilience (the delta shows how much resilience improves)
A side-by-side bar chart comparing current vs. post-diversification spend per vendor
A detail table showing exactly how much money moves from which vendor to which
This is a "what-if" tool. It doesn't change any data — it just shows the math of what diversification would look like.

### Tab 2: 🔎 Golden Record Dossier
This answers: "Tell me everything about this specific organization across every government dataset."
You enter a Business Number (BN) — the 9-digit identifier that the Canada Revenue Agency assigns to every registered entity. The dashboard then searches two datasets simultaneously:
CRA side (left card): Pulls from the CRA T3010 charity filings database. Shows the organization's legal name, charity category, designation (charitable organization vs. public foundation vs. private foundation), location, registration date, and which fiscal years they've filed returns for.
FED side (right card): Pulls from the federal Grants & Contributions database. Shows total dollar value of all grants received, how many grants, which federal departments funded them, which programs, and a table of the 5 largest individual grants.
Risk Flags appear at the top if the data reveals concerns:
🔴 High federal funding (> $1M total)
🟡 High grant volume (> 20 grants)
🟡 Single-department dependency (all grants from one department)
🔴 Entity receives federal grants but has NO CRA charity registration (this is a red flag — who is this entity?)
The power here is the cross-reference. CRA and FED are separate government systems that don't talk to each other. Lens joins them on the Business Number to build a unified picture.

### Tab 3: ☀️ Funding Sunburst
A Plotly sunburst chart that visualizes the flow of federal money as concentric rings:
Inner ring: Federal departments (e.g., "Agriculture and Agri-Food Canada")
Middle ring: Grant type — G (Grant), C (Contribution), or O (Other transfer payment). These are legally distinct: a Grant has fewer conditions, a Contribution has performance requirements.
Outer ring: Top recipient organizations
Click any segment to zoom in. Hover to see dollar values and the percentage of the parent segment.
The slider controls how many departments to show (top 5 to top 20 by total value).
The three metrics below the chart:
Total Grant Value — Sum of all agreement_value for non-amendment records
Departments — Count of distinct federal departments in the data
Unique Recipients — Count of distinct recipient organizations
This data comes from the live Open Canada API, fetched into your local PostgreSQL.

### Tab 4: 🤖 Strategic Analyst
This takes the top high-risk vendors (those with ≥ 20% market share, or the top 5 if none hit 20%) and sends them to an LLM to generate Accountability Briefs — structured investigative memos.
Each memo has three sections:
Profile Summary — Who is this entity and why does it warrant scrutiny
Red Flags — Specific concentration risks, sole-source dependency, discrepancies
Recommended Actions — Concrete next steps for investigation
With LLM_PROVIDER=bedrock, this is a live Claude call. With LLM_PROVIDER=cohere, it uses Cohere Command R+. With placeholder, it returns a template.

### Tab 5: 🔒 Security Audit
A file scanner that checks the S3 mount and optionally the hackathon repo for security issues:
Unencrypted private keys (.pem, .key, .pfx files)
Credential files (.env, credentials.json, service-account.json)
Leaked keys in CSV headers (columns named "api_key", "password", "secret_key", etc.)
Secret values in data files (AWS access keys like AKIA..., GitHub PATs like ghp_..., private key headers)
Each finding is severity-coded:
🔴 HIGH — Actual secrets or private keys found in data files
🟡 MEDIUM — Environment files that might contain secrets
🟢 LOW — Access issues or informational notes
A clean scan shows a green "✅ CLEAN" banner.

Where the Data Comes From
What
Source
How it gets here
Procurement data (Overview tab)
S3 bucket CSV or bundled sample_data.csv
Loaded at startup from ../data/agency-s3/ or fallback
Federal grants (Sunburst, Dossier)
Open Canada API
fetch_opencanada.py pulls from the live CKAN API into local PostgreSQL
CRA charity data (Dossier)
CRA T3010 open data
Loaded from PostgreSQL (when JSONL data bundle is imported)
AI analysis
Amazon Bedrock / Cohere / Gemini
Live API calls using keys in .env


### The Pitch (30 seconds)
"Lens connects three disconnected government datasets — CRA charity filings, federal grants, and provincial procurement — into one dashboard. It calculates real concentration risk metrics used by antitrust regulators, lets you search any organization by Business Number to see every public dollar that flowed to them across jurisdictions, and uses AI to generate investigative risk briefings. The data is live from the Government of Canada's open data API. We built it in a weekend."
