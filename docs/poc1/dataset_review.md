
| Dataset | Relevance to KinderCompass Pipeline |
| :--- | :--- |
| Listing of Centres | Stage 1 (Search & Match): Provides the metadata (name, operator type) to populate the core preschool nodes in Neo4j Knowledge Graph. |
| Listing of Centre Services | Stage 2 (Compliance & Cost): Contains the exact variables (Levels Offered, Citizenship, Fees) the Rules Engine needs to determine base tuition before applying ECDA subsidies. |
| Pre-Schools Location | Stage 3 (Route Planning): The GEOJSON format provides the exact spatial coordinates your Genetic Algorithm needs to plot and optimize the travel route. |
| Listing of Centres Licence History | Quality Filter: ECDA awards longer licence tenures (e.g., 36 months vs. 12 months) to centers with excellent track records. This acts as a great proxy for a "quality rating" within your Knowledge Graph. |

These sources give us the structural data required to execute the project properly.

To make the system work, data must flow seamlessly between these modules. For example, when a parent selects a school in Stage 1, the Rules Engine in Stage 2 needs to look up that exact school's fee structure in the "Listing of Centre Services" dataset.

The best field to use as the unique identifier across all four datasets is the Centre Code (centre_code).

While a preschool brand might have dozens of locations across Singapore, the centre_code is unique to each specific physical branch. This ensures that when our pipeline runs, it perfectly matches a school's pedagogy from the Knowledge Graph to its exact fees in the Rules Engine and its precise map coordinates for the Genetic Algorithm.

We need to prepare this data for the architecture and we should clean and merge these different files before loading them into the system.

Using Pandas in python script:

Listing of Centre Services has multiple rows for each single centre_code, doing a standard flat merge() or join() right away would duplicate the preschool's basic information across dozens of rows.

Options for Pandas Preprocessing 
  - Option 1: 

     Two Separate Clean DataFrames (Relational Approach)
     
     Main Centre Table: \
       - Merge Listing of Centres, Pre-Schools Location, and Licence History into a single flat DataFrame (1 row per centre_code).  
     
     Services Lookup Table: \
       - Keep Listing of Centre Services as its own separate DataFrame indexed by centre_code. 
     
     Why it works:

     Stage 1 Knowledge Graph can ingest the main table cleanly for nodes and coordinates. Stage 2 Rules Engine can quickly filter the services table by centre_code, service_type, and citizenship when calculating costs.

     Simplicity: It uses standard Pandas functions like pd.merge(), which are generally easier to write and debug if data gets messy.

     Neo4j Friendly: Graph databases excel at importing flat CSV files where one row equals one node. The main table serves as a perfect blueprint for your Preschool nodes.

 - Option 2: 

   Nested JSON Aggregation (Single DataFrame Approach) Use .groupby('centre_code') in Pandas to combine all service/fee rows for a center into a single dictionary or list of JSON objects inside a services column. 

   Why it works:

   Single File Management: You only have one consolidated dataset to load and pass between your backend modules and your frontend UI.

   No Runtime Joins: Because all the fees and services are bundled directly inside the preschool's main row, the system never has to cross-reference a second table when pulling information.

   Modern API Structure: Nested JSON is the standard data format used in modern web development. 

Lets use Option2.

There are two main steps:
   
The Base: Merge the three 1-to-1 datasets (Listing of Centres, Pre-Schools Location, and Licence History) into one flat table using pd.merge().  
   
The JSON Aggregation: Group the 1-to-many dataset (Listing of Centre Services) into JSON objects and attach it to that base table. This is the core of Option 2

We need to decide what information actually goes inside that JSON object for each preschool. 

Thinking about what your Rules Engine needs to calculate the correct subsidy in Stage 2, which specific columns from the Listing of Centre Services dataset do we need to pack into our JSON dictionary?

To make sure Stage 2 Rules Engine has exactly what it needs to calculate subsidies and check eligibility, we pack these four specific columns from the Listing of Centre Services dataset into the JSON object: 

  - levels_offered: (e.g., Infant Care, Playgroup) The Rules Engine needs this to verify if the center matches the child's age.  
  - type_of_service: (e.g., Full Day, Half Day) Fees change drastically based on whether the parent needs full-day or half-day care.
  - type_of_citizenship: (e.g., SC, SPR, Foreigner) This determines the baseline tuition cost before working-mother subsidies are even applied. 
  - fees: The actual gross numerical cost that the Rules Engine will use as the starting point for its math.  
  
  By bundling these four columns together, every preschool row in the final Pandas DataFrame will contain a complete, self-contained pricing menu.