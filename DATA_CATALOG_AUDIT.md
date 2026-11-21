# 2014–2026 Maintenance Coverage and Verification Gate

**As of 2026-11-21: NOT COMPLETE.** This document is an evidence and gap audit, not a certification of a full 2014–2026 maintenance database.

## Scope

Four US cargo-van platforms across the 2014–2026 target years generate 52 model-year cells. The 2014 full-size Ford Transit is **not applicable** in the US market (the 2015 model year replaced the E-Series full-size van), leaving 51 potentially applicable cells. These cells are not full powertrain combinations.

FleetIQ deliberately maintains two different concepts:
- **An OEM-backed interval for a specific task**: a sourced schedule row with its mode, condition, model year and applicability.
- **Fully audited vehicle configuration**: every applicable scheduled task, service monitor, severe-duty exception, engine and drivetrain option has been checked against an OEM manual. **No configuration has yet been certified complete.**

The site displays a full year-by-year coverage audit, downloadable as CSV. A yellow cell means one or more verified OEM-backed operations, **not** full maintenance completeness. The goal is 2014–2026 *manufacturer service schedule coverage*, not 2014–2026 predicted mechanical failure outcomes.

## Verified source samples

- **Ford Transit 2020:** [Ford 2020 normal maintenance](https://www.fordservicecontent.com/Ford_Content/vdirsnet/OwnerManual/Home/Content?ProcUid=G2102265&Uid=G2102264&buildtype=web&countryCode=USA&div=f&languageCode=en&userMarket=usa&vFilteringEnabled=False&variantid=7386), sourced normal monitor caps and selected periodic services.
- **Ford Transit 2021:** [Ford 2021 owner's manual second printing](https://www.fordservicecontent.com/Ford_Content/Catalog/owner_information/2021-Ford-Transit-Owners-Manual-version-2_om_EN-US_04_2021.pdf), Scheduled Maintenance (normal and special-operating-condition sections); oil monitor ceiling, brake fluid, cabin/engine air filters, spark plugs, transmission and dusty-duty cap.
- **Ford Transit 2022:** [Ford 2022 normal maintenance for gasoline powertrains](https://www.fordservicecontent.com/Ford_Content/vdirsnet/OwnerManual/Home/Content?ProcUid=G2203750&Uid=G2203749&buildtype=web&countryCode=USA&div=f&languageCode=en&userMarket=usa&vFilteringEnabled=False&variantid=8416), sourced selected monitor, brake, filter, transmission and gasoline spark-plug intervals.
- **Ford Transit 2023:** [Ford 2023 normal maintenance](https://www.fordservicecontent.com/Ford_Content/vdirsnet/OwnerManual/Home/Content?ProcUid=G2203750&buildtype=web&countryCode=USA&div=f&languageCode=en&userMarket=USA&vFilteringEnabled=False&variantid=9103), selected intervals and use-conditions only.
- **Ram ProMaster 2018:** [Official 2018 ProMaster user guide](https://vehicleinfo.mopar.com/assets/publications/en-us/Ram/2018/ProMaster/104377_18_VF_UG_EN_USC_DIGITAL_E4_V1.pdf), pp. 102–105: oil-life monitor maximum, severe-duty oil cap, air filters, brake fluid and spark-plug maintenance. Initial coolant service remains advisory-only because recurrent intervals were not established.
- **Ram ProMaster 2019:** [Official 2019 ProMaster user guide](https://vehicleinfo.mopar.com/assets/publications/en-us/Ram/2019/ProMaster/104374_19_VF_UG_EN_USC_DIGITAL_E1_V1.pdf), pp. 102–104: normal and severe oil service, filters, 2-year brake fluid and 100,000-mile spark plugs.
- **Ford Transit 2024 gasoline:** [Ford 2024 Transit owner's manual](https://www.fordservicecontent.com/Ford_Content/Catalog/owner_information/2024_Ford_Transit_Owners_Manual_version_1_om_EN-US.pdf), Scheduled Maintenance pp. 530–532: normal gasoline brake fluid, filters, spark plugs, transmission service and first coolant replacement advisory. Battery-electric Transit requirements are separate and not inherited.
- **Ram ProMaster 2020:** [Ram 2020 ProMaster owner manual](https://vehicleinfo.mopar.com/assets/publications/en-us/Ram/2020/ProMaster/104365_20_VF_OM_EN_USC_DIGITAL_E2_V2.pdf), service indicator and severe-duty distinctions.
- **Chevrolet Express 2020:** [GM 2020 Express manual](https://www.chevrolet.com/ownercenter/content/dam/gmownercenter/gmna/dynamic/manuals/2020/chevrolet/express/2020-chevrolet-express-owners-manual.pdf), selected normal and severe-duty intervals.
- **Chevrolet Express 2021:** [GM 2021 Express manual](https://www.chevrolet.com/ownercenter/content/dam/gmownercenter/gmna/dynamic/manuals/2021/chevrolet/express/2021-chevrolet-express-owners-manual.pdf), pp. 253–255, tire/required services, air-filter replacement, brake-fluid interval and conditional transmission schedule.
- **Mercedes-Benz Sprinter 2020:** [Mercedes Sprinter marketing overview](https://www.mbvans.com/en/sprinter); **advisory only**; *not* a manufacturer-verified engine-specific maintenance interval.

## Required before a full-catalog completion claim

1. Retrieve the US-specific OEM maintenance book for **each applicable year** and powertrain, including discontinued engines, diesel, gasoline, automatic, AWD and severe-duty applicability.
2. Record exact manual edition, page/section, year, engine, operation, interval mileage, time, engine-hours, one-time versus recurring mode, operating conditions, VIN/equipment notes and source URL.
3. Independently validate extracted tasks, spot-check against original table images, and reconcile conflicting manual editions or bulletin supersessions.
4. Track **applicable model-year-powertrain-usage combinations** and score complete only when required services and condition exceptions have coverage.
5. Add cost ranges with known configuration/geographic scopes separately from OEM schedules.
6. Run CI gates for duplicate intervals, impossible values, missing documents, unsupported cross-year interval reuse, and coverage gaps.
7. Do not produce a maintenance due-date prediction from missing service history, advisory copy, or customer complaints.

## Current limitations

Some 2018–2024 van years have *partial* sourced entries. Most of 2014–2026 still have no verified schedule rows. Zero maintenance entries means **unverified**, not zero scheduled services. Ford E-Transit battery-electric schedules differ from gasoline Transit schedules and must not inherit them. The vehicle cutaway reports NHTSA complaint-share descriptions, not mechanical failure hazards or rates.

**Outcome:** the year matrix is complete as an inventory; the maintenance database is not. Predictive maintenance will require actual verified failures and nonfailure exposure, beyond manufacturer-prescribed service tasks.
