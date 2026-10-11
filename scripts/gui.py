print("1 - gui.py started")

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import shutil
import os
from PIL import Image, ImageTk

print("2 - Tkinter imported")

from analysis_engine import run_analysis

print("3 - analysis_engine imported")

# --------------------------------------------------#
# APPLICATION WINDOW                                #
# --------------------------------------------------#
root = tk.Tk()

print("4 - Tk root created")

root.title("Wisconsin Nitrate & Cancer Analysis")
root.geometry("1100x650")
root.resizable(False, False)

### CREATING THE MAIN CONTAINER ###
main_frame = ttk.Frame(root, padding=20)
main_frame.pack(fill="both", expand=True)


### ADDING A TITLE ###
title_label = ttk.Label(
    main_frame,
    text="Wisconsin Nitrate & Cancer Analysis",
    font=("Segoe UI", 18, "bold")
)
title_label.pack(pady=(0, 20))


### CREATING CONTENT AREA ###
content_frame = ttk.Frame(main_frame)
content_frame.pack(fill="both", expand=True)

left_frame = ttk.Frame(content_frame)
left_frame.pack(side="left", fill="both", expand=True, padx=(0, 15))


### ORIGINAL NON-TABBED MAP FRAME ###
# map_frame = ttk.LabelFrame(
#     content_frame,
#     text="Nitrate Map",
#     padding=10
# )
# map_frame.pack(side="right", fill="both", expand=True)

# map_label = ttk.Label(
#     map_frame,
#     text="Run the analysis to display the map."
# )
# map_label.pack(expand=True)


### CREATING MAP AND SCATTERPLOT TABS ###
visual_frame = ttk.LabelFrame(
    content_frame,
    text="Analysis Visualizations",
    padding=10
)
visual_frame.pack(side="right", fill="both", expand=True)

notebook = ttk.Notebook(visual_frame)                    # Create tabbed display
notebook.pack(fill="both", expand=True)

map_tab = ttk.Frame(notebook)                            # Map tab
scatterplot_tab = ttk.Frame(notebook)                    # Scatterplot tab

notebook.add(map_tab, text="Nitrate Map")                # Add map tab
notebook.add(scatterplot_tab, text="Scatterplot")        # Add scatterplot tab

map_label = ttk.Label(
    map_tab,
    text="Run the analysis to display the nitrate map."
)
map_label.pack(fill="both", expand=True)

scatterplot_label = ttk.Label(
    scatterplot_tab,
    text="Run the analysis to display the scatterplot."
)
scatterplot_label.pack(fill="both", expand=True)


### ADDING k INPUT ###
input_frame = ttk.LabelFrame(
    left_frame,
    text="Analysis Parameters",
    padding=15
)
input_frame.pack(fill="x", pady=(0, 15))

ttk.Label(
    input_frame,
    text="IDW exponent k:"
).grid(row=0, column=0, sticky="w", padx=(0, 10))

k_var = tk.StringVar(value="1.5")

k_entry = ttk.Entry(
    input_frame,
    textvariable=k_var,
    width=10
)
k_entry.grid(row=0, column=1, sticky="w")

ttk.Label(
    input_frame,
    text="k must be greater than 1"
).grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))


### DISPLAYING RESULTS ###
results_frame = ttk.LabelFrame(
    left_frame,
    text="Regression Results",
    padding=15
)
results_frame.pack(fill="both", expand=True, pady=(0, 15))


### CREATING STATISTICAL VARIABLES FOR TKINTER ###
coefficient_var = tk.StringVar(value="—")
r_squared_var = tk.StringVar(value="—")
p_value_var = tk.StringVar(value="—")
observations_var = tk.StringVar(value="—")
conclusion_var = tk.StringVar(value="Run the analysis to view results.")


### ADDING LABELS ###
ttk.Label(results_frame, text="Nitrate coefficient:").grid(
    row=0, column=0, sticky="w", pady=4
)
ttk.Label(results_frame, textvariable=coefficient_var).grid(
    row=0, column=1, sticky="w"
)

ttk.Label(results_frame, text="R²:").grid(
    row=1, column=0, sticky="w", pady=4
)
ttk.Label(results_frame, textvariable=r_squared_var).grid(
    row=1, column=1, sticky="w"
)

ttk.Label(results_frame, text="p-value:").grid(
    row=2, column=0, sticky="w", pady=4
)
ttk.Label(results_frame, textvariable=p_value_var).grid(
    row=2, column=1, sticky="w"
)

ttk.Label(results_frame, text="Observations:").grid(
    row=3, column=0, sticky="w", pady=4
)
ttk.Label(results_frame, textvariable=observations_var).grid(
    row=3, column=1, sticky="w"
)

ttk.Label(
    results_frame,
    text="Conclusion:",
    font=("Segoe UI", 10, "bold")
).grid(
    row=4, column=0, sticky="nw", pady=(15, 4)
)

ttk.Label(
    results_frame,
    textvariable=conclusion_var,
    wraplength=500
).grid(
    row=5,
    column=0,
    columnspan=2,
    sticky="w"
)


### ADDING A STATUS MESSAGE ###
status_var = tk.StringVar(value="Ready.")
current_map_file = tk.StringVar(value="")                # Store current map PNG path

status_label = ttk.Label(
    left_frame,
    textvariable=status_var
)
status_label.pack(anchor="w", pady=(0, 10))


### INPUT VALIDATION ###
def get_k_value():
    try:
        k = float(k_var.get())
    except ValueError:
        raise ValueError("Please enter a numeric value for k.")

    if k <= 1:
        raise ValueError("IDW exponent k must be greater than 1.")

    return k


### CONNECTING THE GUI AND ANALYSIS ENGINE ###
def run_analysis_clicked():
    try:
        k = get_k_value()
    except ValueError as error:
        messagebox.showerror(
            "Invalid k Value",
            str(error)
        )
        status_var.set(str(error))
        return

    run_button.config(state="disabled")
    save_map_button.config(state="disabled")
    status_var.set(f"Running analysis for k = {k}...")

    thread = threading.Thread(
        target=run_analysis_worker,
        args=(k,),
        daemon=True
    )

    thread.start()


### ADDING A WORKER FUNCTION ALLOWING ARCPY TO RUN INDEPENDENTLY OF TKINTER ###
def run_analysis_worker(k):
    try:
        results = run_analysis(k)

        root.after(
            0,
            lambda: display_results(results)
        )

    except Exception as error:
        root.after(
            0,
            lambda error=error: display_error(error)
        )


### DISPLAY AND RESIZE IMAGES ###
def display_image(file_path, label):
    """Load a PNG, resize it, and display it in Tkinter."""

    with Image.open(file_path) as source:
        image = source.copy()                            # Load generated PNG
    image.thumbnail((500, 390), Image.Resampling.LANCZOS) # Fit within panel
    photo = ImageTk.PhotoImage(image)                    # Convert to Tkinter image
    label.config(image=photo, text="")                   # Display image
    label.image = photo                                 # Prevent garbage collection


### DISPLAY REGFRESSION RESULTS ###
def display_results(results):
    regression = results["regression"]

    coefficient_var.set(
        f'{regression["coefficient"]:.6f}'
    )

    r_squared_var.set(
        f'{regression["r_squared"]:.6f}'
    )

    p_value_var.set(
        f'{regression["p_value"]:.6g}'
    )

    observations_var.set(
        str(regression["observations"])
    )

    conclusion_var.set(
        regression["conclusion"]
    )

    # status_var.set("Analysis complete.")

    # run_button.config(state="normal")

    # map_file = results["map_file"]                            # Get generated map PNG
    # map_image = tk.PhotoImage(file=map_file)                  # Load PNG into Tkinter

    # map_label.config(
    #     image=map_image,
    #     text=""
    # )

    # map_label.image = map_image                               # Keep image in memory

    try:
        display_image(results["map_file"], map_label)                  # Show nitrate map
        display_image(results["scatterplot_file"], scatterplot_label) # Show scatterplot

        current_map_file.set(results["map_file"])                     # Store latest map path
        save_map_button.config(state="normal")                        # Enable Save Map

        status_var.set("Analysis complete.")                          # Update status

    except (OSError, KeyError) as error:
        display_error(error)                                         # Report missing/invalid image

    finally:
        run_button.config(state="normal")                             # Re-enable Run Analysis


### ERROR HANDLING ###
def display_error(error):
    status_var.set("Analysis failed.")

    run_button.config(state="normal")

    messagebox.showerror(
        "Analysis Error",
        str(error)
    )


### SAVE MAP ###
def save_map():
    """Save the generated nitrate map to a user-selected location."""

    source_file = current_map_file.get()                 # Get latest generated map

    if not source_file or not os.path.isfile(source_file):
        messagebox.showerror(
            "Save Error",
            "No nitrate map is available to save."
        )
        return

    destination = filedialog.asksaveasfilename(
        title="Save Nitrate Map",
        defaultextension=".png",
        filetypes=[("PNG Image", "*.png")],
        initialfile=os.path.basename(source_file)
    )

    if not destination:
        return                                          # User cancelled

    try:
        shutil.copyfile(source_file, destination)        # Copy PNG to selected location
        status_var.set("Map saved successfully.")
        messagebox.showinfo(
            "Save Map",
            f"Map saved to:\n{destination}"
        )

    except OSError as error:
        messagebox.showerror("Save Error", str(error))


### ADDING RUN ANALYSIS BUTTON ###
run_button = ttk.Button(
    left_frame,
    text="Run Analysis",
    command=run_analysis_clicked
)
run_button.pack(pady=(5, 15))


### ADDING SAVE MAP BUTTON ###
save_map_button = ttk.Button(
    left_frame,
    text="Save Map",
    command=save_map,
    state="disabled"                                    # Enabled after analysis
)
save_map_button.pack(pady=(0, 15))


### START TKINTER ###
print("5 - entering Tkinter mainloop")

root.mainloop()

print("6 - mainloop ended")