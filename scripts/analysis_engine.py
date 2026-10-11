import arcpy                                                        # Esri’s Python library for automating GIS operations, including IDW, zonal statistics, joins, spatial processing, and map export.
from arcpy.sa import Idw, RadiusVariable, ZonalStatisticsAsTable    # Importing funtions from ArcPy
import os                                                           # Importing os to access local operating system features (mikedir, getcwd, etc.)
from scipy.stats import linregress                                  # Importing Linear Regression function from SciPy
import matplotlib
matplotlib.use("Agg")                                               # Non-GUI backend for creating image files in worker thread
import matplotlib.pyplot as plt                                     #


# --------------------------------------------------#
# PROJECT CONFIGURATION                             #
# --------------------------------------------------#

GDB = r"C:\Users\Jonny\OneDrive\Desktop\UW GIS G777 Capstone in GIS Development\GEOG777_Project1\aprx\GEOG777_Project1\GEOG777_Project1.gdb"    # Define location data directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(GDB)))                                                                           # Project folder
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")                                                                                              # Export folder
os.makedirs(OUTPUT_DIR, exist_ok=True)                                                                                                          # Ensure folder exists

WELLS = os.path.join(GDB, "well_nitrate_projWitm")                  #
TRACTS = os.path.join(GDB, "cancer_tracts_projWitm")

NITRATE_FIELD = "nitr_ran"
TRACT_ID_FIELD = "GEOID10"
CANCER_FIELD = "canrate"
MEAN_NITRATE_FIELD = "MEAN"

CELL_SIZE = 250
SEARCH_POINTS = 12

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True


# --------------------------------------------------#
# FUNCTIONS                                         #
# --------------------------------------------------#

### VALIDATE INPUT FILES ARE AVAILABLE ###
def validate_inputs():
    if not arcpy.Exists(WELLS):
        raise FileNotFoundError(f"Well dataset not found: {WELLS}")

    if not arcpy.Exists(TRACTS):
        raise FileNotFoundError(f"Tract dataset not found: {TRACTS}")

    
### HELPER FUNCTION FOR k ###
def format_k(k):
    """Convert a k value such as 1.5 into a GIS-safe label such as k15."""
    
    if k <= 1:
        raise ValueError("IDW exponent k must be greater than 1.")
    
    return f"k{int(round(k * 10))}"


### IDW FUNCTION ###
def run_idw(k):
    """
    Interpolate nitrate measurements from wells into a continuous raster.
    """

    k_name = format_k(k)

    output_raster = os.path.join(
        GDB,
        f"test_idw_nitrate_{k_name}_250m"
    )

    print(f"Running IDW with k = {k}...")

    idw_result = Idw(
        in_point_features=WELLS,
        z_field=NITRATE_FIELD,
        cell_size=CELL_SIZE,
        power=k,
        search_radius=RadiusVariable(SEARCH_POINTS)
    )

    idw_result.save(output_raster)

    print(f"Created: {output_raster}")

    return output_raster


### ZONAL STATISTICS ###
def run_zonal_statistics(idw_raster, k):
    """
    Calculate mean interpolated nitrate for each census tract.
    """

    k_name = format_k(k)

    output_table = os.path.join(
        GDB,
        f"test_mean_tract_nitrate_{k_name}"
    )

    print("Calculating mean nitrate by census tract...")

    ZonalStatisticsAsTable(
        in_zone_data=TRACTS,
        zone_field=TRACT_ID_FIELD,
        in_value_raster=idw_raster,
        out_table=output_table,
        ignore_nodata="DATA",
        statistics_type="MEAN"
    )

    print(f"Created: {output_table}")

    return output_table


### AUTOMATE ADD JOIN → EXPORT → REMOVE JOIN ###
def create_joined_tracts(mean_table, k):
    """
    Temporarily join mean nitrate to cancer tracts,
    export the joined result, then remove the temporary join.
    """

    k_name = format_k(k)

    output_features = os.path.join(
        GDB,
        f"test_joined_tracts_nitrate_{k_name}"
    )

    temp_layer = "cancer_tracts_temp"

    print("Creating temporary tract layer...")

    arcpy.management.MakeFeatureLayer(
        TRACTS,
        temp_layer
    )

    try:
        print("Joining mean nitrate to census tracts...")

        arcpy.management.AddJoin(
            in_layer_or_view=temp_layer,
            in_field=TRACT_ID_FIELD,
            join_table=mean_table,
            join_field=TRACT_ID_FIELD,
            join_type="KEEP_ALL"
        )

        print("Exporting permanent joined tract layer...")

        arcpy.conversion.ExportFeatures(
            temp_layer,
            output_features
        )

        print(f"Created: {output_features}")

    finally:
        # Cleanup happens even if export fails.
        print("Removing temporary join...")

        try:
            arcpy.management.RemoveJoin(temp_layer)
        except Exception:
            pass

        print("Deleting temporary feature layer...")

        if arcpy.Exists(temp_layer):
            arcpy.management.Delete(temp_layer)

    return output_features


### REGRESSION ###
def run_regression(joined_tracts, k):
    """
    Run linear regression of cancer rate on mean nitrate.
    Create predicted values and residuals for each census tract.
    """

    k_name = format_k(k)

    output_features = os.path.join(
        GDB,
        f"test_regress_cancer_nitrate_{k_name}"
    )

    print("Running linear regression...")

    # Make a permanent regression output feature class.
    arcpy.management.CopyFeatures(
        joined_tracts,
        output_features
    )

    # Read nitrate and cancer values.
    nitrate_values = []
    cancer_values = []

    with arcpy.da.SearchCursor(
        output_features,
        [MEAN_NITRATE_FIELD, CANCER_FIELD]
    ) as cursor:

        for mean_nitrate, cancer_rate in cursor:

            if mean_nitrate is not None and cancer_rate is not None:
                nitrate_values.append(mean_nitrate)
                cancer_values.append(cancer_rate)

    if len(nitrate_values) < 2:
        raise ValueError(
            "Not enough valid nitrate/cancer observations for regression."
        )

    # Run ordinary linear regression.
    regression = linregress(
        nitrate_values,
        cancer_values
    )

    coefficient = regression.slope
    intercept = regression.intercept
    p_value = regression.pvalue
    r_squared = regression.rvalue ** 2

    # Add fields for tract-level predictions and residuals.
    existing_fields = {
        field.name.upper()
        for field in arcpy.ListFields(output_features)
    }

    if "PREDICTED" not in existing_fields:
        arcpy.management.AddField(
            output_features,
            "PREDICTED",
            "DOUBLE"
        )

    if "RESIDUAL" not in existing_fields:
        arcpy.management.AddField(
            output_features,
            "RESIDUAL",
            "DOUBLE"
        )

    # Calculate predicted cancer rate and residual for every tract.
    with arcpy.da.UpdateCursor(
        output_features,
        [
            MEAN_NITRATE_FIELD,
            CANCER_FIELD,
            "PREDICTED",
            "RESIDUAL"
        ]
    ) as cursor:

        for row in cursor:

            mean_nitrate = row[0]
            cancer_rate = row[1]

            if mean_nitrate is None or cancer_rate is None:
                continue

            predicted = intercept + coefficient * mean_nitrate
            residual = cancer_rate - predicted

            row[2] = predicted
            row[3] = residual

            cursor.updateRow(row)

    # Plain-English interpretation.
    if p_value < 0.05:

        if coefficient > 0:
            conclusion = (
                "Mean nitrate has a statistically significant "
                "positive linear association with cancer rate."
            )

        elif coefficient < 0:
            conclusion = (
                "Mean nitrate has a statistically significant "
                "negative linear association with cancer rate."
            )

        else:
            conclusion = (
                "Mean nitrate has a statistically significant "
                "relationship with cancer rate."
            )

    else:
        conclusion = (
            "The analysis does not show a statistically significant "
            "linear association between mean nitrate and cancer rate."
        )

    print("--------------------------------------")
    print("Regression results")
    print("--------------------------------------")
    print(f"Coefficient: {coefficient:.6f}")
    print(f"Intercept:   {intercept:.6f}")
    print(f"R-squared:   {r_squared:.6f}")
    print(f"P-value:     {p_value:.6g}")
    print(f"Observations:{len(nitrate_values)}")
    print(f"Conclusion:  {conclusion}")

    return {
        "output_features": output_features,
        "coefficient": coefficient,
        "intercept": intercept,
        "r_squared": r_squared,
        "p_value": p_value,
        "observations": len(nitrate_values),
        "conclusion": conclusion
    }


# ### CREATE MAP - TRACT CENTROIDS (POINTS) ###
# def create_map(joined_tracts, k):
#     """Create a PNG map of mean nitrate by census tract."""

#     k_name = format_k(k)                                      # Format k for filename
#     map_file = os.path.join(GDB, f"map_nitrate_{k_name}.png") # Map output path

#     print("Creating nitrate map...")

#     x_values = []                                             # Polygon x coordinates
#     y_values = []                                             # Polygon y coordinates
#     nitrate_values = []                                       # Mean nitrate values

#     with arcpy.da.SearchCursor(
#         joined_tracts,
#         ["SHAPE@XY", MEAN_NITRATE_FIELD]
#     ) as cursor:
#         for coordinates, mean_nitrate in cursor:
#             if mean_nitrate is not None:
#                 x_values.append(coordinates[0])
#                 y_values.append(coordinates[1])
#                 nitrate_values.append(mean_nitrate)

#     plt.figure(figsize=(8, 7))                                # Create map figure

#     points = plt.scatter(
#         x_values,
#         y_values,
#         c=nitrate_values,
#         s=12
#     )

#     plt.colorbar(points, label="Mean Nitrate")                # Add nitrate legend
#     plt.title(f"Mean Nitrate by Census Tract — k = {k}")       # Add map title
#     plt.xlabel("Easting")
#     plt.ylabel("Northing")
#     plt.tight_layout()

#     plt.savefig(map_file, dpi=150)                            # Save PNG
#     plt.close()

#     print(f"Created map: {map_file}")

#     return map_file


### CREATE MAP - CHRORPLETH TRACTS ###
def create_map(joined_tracts, k):
    """Create a PNG choropleth map of mean nitrate by census tract."""

    k_name = format_k(k)                                      # Format k for filename
    # map_file = os.path.join(GDB, f"map_nitrate_{k_name}.png") # Map output path
    map_file = os.path.join(OUTPUT_DIR, f"map_nitrate_{k_name}.png")  # Save PNG outside geodatabase

    print("Creating nitrate map...")

    fig, ax = plt.subplots(figsize=(6, 6))                     # Create map figure

    nitrate_values = []

    with arcpy.da.SearchCursor(
        joined_tracts,
        [MEAN_NITRATE_FIELD]
    ) as cursor:
        for row in cursor:
            if row[0] is not None:
                nitrate_values.append(row[0])

    min_nitrate = min(nitrate_values)                          # Minimum for color scale
    max_nitrate = max(nitrate_values)                          # Maximum for color scale

    cmap = plt.get_cmap("viridis")                             # Map color ramp
    norm = plt.Normalize(min_nitrate, max_nitrate)             # Normalize nitrate values

    with arcpy.da.SearchCursor(
        joined_tracts,
        ["SHAPE@", MEAN_NITRATE_FIELD]
    ) as cursor:

        for geometry, mean_nitrate in cursor:

            if geometry is None or mean_nitrate is None:
                continue

            color = cmap(norm(mean_nitrate))                   # Color based on nitrate

            for part in geometry:

                x = []
                y = []

                for point in part:
                    if point:
                        x.append(point.X)
                        y.append(point.Y)

                if x and y:
                    ax.fill(
                        x,
                        y,
                        facecolor=color,
                        edgecolor="white",
                        linewidth=0.1
                    )

    scalar_map = plt.cm.ScalarMappable(norm=norm, cmap=cmap)   # Create legend scale
    scalar_map.set_array([])

    fig.colorbar(
        scalar_map,
        ax=ax,
        label="Mean Nitrate"
    )

    ax.set_title(f"Mean Nitrate by Census Tract — k = {k}")    # Map title
    ax.set_aspect("equal")
    ax.axis("off")                                             # Hide map coordinates

    plt.tight_layout()
    plt.savefig(map_file, dpi=100, bbox_inches="tight")        # Save PNG
    plt.close(fig)

    print(f"Created map: {map_file}")

    return map_file


### CREATE REGRESSION SCATTERPLOT ###
def create_scatterplot(regression_results, k):
    """Plot mean nitrate against cancer rate with a fitted regression line."""

    k_name = format_k(k)                                                # Format k for filename
    plot_file = os.path.join(OUTPUT_DIR, f"scatterplot_{k_name}.png")    # Output PNG

    print("Creating regression scatterplot...")

    x_values = []                                                        # Mean nitrate
    y_values = []                                                        # Cancer rate

    with arcpy.da.SearchCursor(
        regression_results["output_features"],
        [MEAN_NITRATE_FIELD, CANCER_FIELD]
    ) as cursor:
        for nitrate, cancer in cursor:
            if nitrate is not None and cancer is not None:
                x_values.append(nitrate)
                y_values.append(cancer)

    coefficient = regression_results["coefficient"]                     # Regression slope
    intercept = regression_results["intercept"]                         # Regression intercept
    r_squared = regression_results["r_squared"]                         # Model R²
    p_value = regression_results["p_value"]                             # Slope p-value

    x_line = [min(x_values), max(x_values)]                              # Regression line endpoints
    y_line = [intercept + coefficient * x for x in x_line]              # Predicted cancer rates

    fig, ax = plt.subplots(figsize=(6, 5))                              # Create figure

    ax.scatter(
        x_values,
        y_values,
        alpha=0.35,
        s=12,
        color="steelblue",
        label="Census tracts"
    )

    ax.plot(
        x_line,
        y_line,
        color="red",
        linewidth=2,
        label="Regression line"
    )

    ax.set_title(f"Nitrate vs. Cancer Rate — k = {k}")                   # Chart title
    ax.set_xlabel("Mean Nitrate")                                       # X axis
    ax.set_ylabel("Cancer Rate")                                        # Y axis

    ax.text(
        0.05, 0.95,
        f"R² = {r_squared:.4f}\np = {p_value:.3g}",
        transform=ax.transAxes,
        verticalalignment="top"
    )

    ax.legend()                                                         # Display legend
    fig.tight_layout()                                                  # Adjust spacing
    fig.savefig(plot_file, dpi=100)                                     # Save PNG
    plt.close(fig)                                                      # Release figure

    print(f"Created scatterplot: {plot_file}")

    return plot_file


### RUN ANALYSIS ###
def run_analysis(k):
    """
    Run the nitrate analysis workflow for a user-supplied IDW exponent.
    """
    arcpy.env.overwriteOutput = True # Overwrites existing files in the directory.
    if arcpy.CheckExtension("Spatial") !="Available":
        raise RuntimeError("Spatial Analyst extension is not available.")

    arcpy.CheckOutExtension("Spatial")

    try:

        print("--------------------------------------")
        print(f"Starting analysis for k = {k}")
        print("--------------------------------------")

        validate_inputs()
        format_k(k)

        idw_raster = run_idw(k)
        mean_table = run_zonal_statistics(idw_raster, k)
        joined_tracts = create_joined_tracts(mean_table, k)
        regression_results = run_regression(joined_tracts, k)
        map_file = create_map(joined_tracts, k)                                         # Create nitrate map
        scatterplot_file = create_scatterplot(regression_results, k)                    # Generate regression scatterplot

        print("--------------------------------------")
        print("Analysis complete.")
        print("--------------------------------------")

        return {
            "idw_raster": idw_raster,
            "mean_table": mean_table,
            "joined_tracts": joined_tracts,
            "regression": regression_results,
            "map_file": map_file,
            "scatterplot_file": scatterplot_file
        }

    finally:
        arcpy.CheckExtension("Spatial")

if __name__ == "__main__":
    results = run_analysis(1.5)
    print(results)
