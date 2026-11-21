# FleetIQ Maintenance & Repair Timing — Evidence and scope

## First release

The **Maintenance timing** tab extends FleetIQ without replacing any of its other nine tabs.

- Select a vehicle, model year and odometer.
- View scoped manufacturer service guidance for **2020** Ford Transit, Ram ProMaster, Chevrolet Express, and Mercedes-Benz Sprinter (the latter marked *advisory only*).
- Choose a service operation and optionally supply the mileage and/or elapsed months since **that operation's own last service**. Show distance to a documented mileage or time limit *only when relevant service history is known*.
- Compare an NHTSA reported-issue category across nearby model years; see distinct complaint counts, count of complaints with mileage, completeness percentage and the median odometer reported in complaints.
- Show topically associated repair-cost reference operations when matching prices exist. They are not diagnoses or recommended replacements.
- Download service assessment and aggregate complaint evidence as CSV.

## Confirmed manufacturer evidence, 2020 model year

- **2020 Ford Transit:** Ford US owner's manual, normal scheduled maintenance: oil-life indicator capped at 10,000 miles / one year; cabin filter 20,000 miles; engine air filter 30,000; brake fluid three years; spark plugs 100,000 for applicable gasoline engines; automatic transmission fluid/filter 150,000 for applicable transmissions. Ford specifies shorter intervals under certain heavy commercial and severe conditions. [Ford 2020 service manual](https://www.fordservicecontent.com/Ford_Content/vdirsnet/OwnerManual/Home/Content?ProcUid=G2102265&Uid=G2102264&buildtype=web&countryCode=USA&div=f&languageCode=en&moidRef=G1612532&userMarket=usa&vFilteringEnabled=False&variantid=7386).
- **2020 Ram ProMaster:** Ram/FCA official 2020 owner's manual: oil-life indicator governs normal service, maximum 10,000 miles / 12 months / 350 engine hours (whichever occurs first), with severe-duty cap of 4,000 miles or 350 hours for dust/off-road/predominant idle. Tire rotation and brake inspection at oil-change events. Engine hours cannot be assessed by the app; check actual dash hour meter if relevant. [Ram ProMaster 2020 owner manual](https://vehicleinfo.mopar.com/assets/publications/en-us/Ram/2020/ProMaster/104365_20_VF_OM_EN_USC_DIGITAL_E2_V2.pdf).
- **2020 Chevrolet Express:** GM's 2020 owner manual maintenance schedule: tire rotations / required service every 7,500 miles (if tire configuration permits), engine air filter 45,000 miles or four years, brake fluid five years, spark plugs per marked schedule at 97,500 miles for applicable engine, severe-service automatic transmission-fluid/filter entries are different from normal schedule. The oil-life monitor controls engine oil service. [2020 Chevrolet Express owner's manual](https://www.chevrolet.com/ownercenter/content/dam/gmownercenter/gmna/dynamic/manuals/2020/chevrolet/express/2020-chevrolet-express-owners-manual.pdf).
- **Mercedes Sprinter:** Mercedes-Benz Vans publicly advertises *up to* 20,000 miles between service visits. That is marketing-level guidance, **not a verified 2020 engine-specific service interval**. The dataset marks it as `advisory`; no next-service mileage is calculated. Consult the applicable Mercedes-Benz 2020 maintenance booklet and service display. [Mercedes Sprinter official page](https://www.mbvans.com/en/sprinter); [model-year manuals](https://www.mbvans.com/en/owner-manuals).

**Coverage warning:** This is not a schedule for all years 2014–2026. Non-2020 vehicle-year selections deliberately do **not** show a different year's service schedule as if it applied.

## Data and code

- `data/maintenance_schedules.csv`: manufacturer-attributed service operations with exact year range, mileage and month limits, duty-cycle/engine scope, original reference URLs, and explanatory limitations.
- `maintenance_intelligence.py`: catalog validation, service assessment logic, complaint-mileage views, optional matching repair-price references, and UI.
- `data/problem_summary.csv`: historical NHTSA complaint-group summaries already derived from the immutable raw complaint dataset.
- `tests/test_maintenance_intelligence.py`: checks for scope, invalid intervals, lack of service history, monitor caps, mileage calculations and sample-coverage safety.
- `.github/workflows/validate_maintenance.yml`: run Python compilation, tests and Streamlit startup with ten tabs.

Run:

```bash
pip install -r requirements.txt pytest
python -m pytest -q tests/test_maintenance_intelligence.py tests/test_repair_intelligence.py
streamlit run app.py
```

## Methodology limitations

1. **Maintenance intervals** are manufacturer recommendations or maximum service limits, not indications that a vehicle is mechanically faulty.
2. **Due/approaching limits** require records for the specific task. All calculations are conditional on user-entered service mileage/months and do not consider engine hours, sensor signals or prior service invoices.
3. **NHTSA complaint mileage** is the odometer stated when the consumer reported a symptom, not a confirmed component failure time, repair mileage or survival-curve sample. Complaints are voluntary and incomplete, and the denominator of in-service vehicles is unknown.
4. **Linked repair costs** are published reference ranges with their own year/trim/region limitations; association by symptom category is not a diagnosis.
5. No predictive failure probabilities, recommended repair timing, or true remaining useful life are claimed.

## Next data priorities

Complete VIN- or configuration-specific manufacturer maintenance coverage for more years, engine and duty cycles. Add last-service history as a per-vehicle per-task field only with informed user consent. Establish verified real-world repair outcomes and mileage denominators before building predictive time-to-failure models.
