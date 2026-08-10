# PoC 1 UI Example

This walkthrough provides one complete set of UI inputs that exercises all
three KinderCompass stages, including the optional 1 km postal-code filter.
Before starting, rebuild the Neo4j graph with the current processed data and
configure `ONEMAP_EMAIL` and `ONEMAP_PASSWORD` in the PoC `.env` file.

## Stage 1: preschool preferences

Enter this message in the preference chatbot:

```text
I am looking for a Montessori preschool
```

Enter this postal code:

```text
548674
```

Select **Only show preschools within 1 km**. OneMap resolves the postal code to
coordinates, and Stage 1 retains matching preschools within 1 km even when a
planning-area boundary lies inside the search radius.

Possible Stage 1 matches include:

| Centre code | Preschool |
|---|---|
| `PT8718` | Masterminds Montessori Sengkang |
| `PT9789` | Leeds Montessori |

The measured straight-line distances in the current location data are
approximately `0.00 km` for PT8718 and `0.09 km` for PT9789. Exact displayed
values depend on the coordinate returned for the entered postal code.

## Stage 2: family details

Enter the following form values:

| Field | Value |
|---|---|
| Child's date of birth | `10 June 2023` |
| Intended admission date | `1 January 2026` |
| Gross household income | `4500` |
| Basic monthly subsidy | `600` |

The prototype calculates the calendar age as `2026 - 2023 = 3`, making the
required care level `Pre-Nursery (3 yrs old)`.

For the current sample data, the estimated monthly fees are:

| Preschool | Estimated monthly fee |
|---|---:|
| Masterminds Montessori Sengkang | $400 |
| Leeds Montessori | $350 |

These amounts use the proof-of-concept subsidy rules and are not official fee
quotations.

## Stage 3: centre and route selection

Select these eligible centres:

```text
PT8718 - Masterminds Montessori Sengkang
```

Enter these location values:

| Field | Value |
|---|---|
| Home postal code | `540231` |
Select **Calculate distance**. The result should contain:

```text
Home
-> Masterminds Montessori Sengkang
```

Results rely on the centre record and coordinates in the current dataset. Stage
3 uses Haversine straight-line distance rather than road distance, traffic, or
estimated travel time.
