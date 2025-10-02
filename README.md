# VITAL: Vessel Integrated Turbine Assessment for LCOE

## Description
VITAL is a Python package designed for the assessment of vessel integrated turbines, aimed at optimizing the Levelized Cost of Energy (LCOE).

## Prerequisites
- Conda should be installed on your system.
- If you don't have Conda installed, you can download it from the official Conda website: [https://www.anaconda.com/download](https://www.anaconda.com/download).
- Ensure that `git` and `pip` are installed on your system.

### Resources
- [Anaconda Tutorial](https://anaconda.cloud/video-gs-installing-anaconda-windows) - A helpful guide for first-time Python users.

## Installation Instructions

### Using Conda
1. Clone or download this repository:
   ``` 
   git clone https://github.com/sandialabs/VITAL.git
   ```

2. Navigate to the project directory:
    ```
    cd vital
    ```

3. Run the following command to create the Conda environment:
    ```
    conda env create --file environment.yml
    ```

This command will install all the required packages listed in the `environment.yml` file. Please note that the installation process might take some time, as Conda will download and install the necessary packages.

4. Once the environment creation process is complete, activate the environment using the following command:
    ```
    conda activate VITAL_env
    ```

This command will activate the newly created environment named `VITAL_env`. You should see the environment name in your terminal prompt.

5. You have successfully set up the Python environment using Conda! Now you can run the tutorial within this environment.

### Using pip
If you prefer to install the package directly using pip, you can do so with the following commands:
1. Clone the repository:
   ``` 
   git clone https://github.com/sandialabs/VITAL.git
   ```

2. Navigate to the project directory:
    ```
    cd vital
    ```

3. Install the package in editable mode:
    ```
    pip install -e .
    ```

This command will install the package and its dependencies, allowing you to make changes to the code and have them reflected immediately.

## Additional Notes
- If you need to deactivate the environment, you can use the following command:
```
conda deactivate
```

- Remember to activate the environment again using `conda activate VITAL_env` whenever you want to work within this environment.

- If you want to remove the environment, you can use the following command:
```
conda env remove --name VITAL_env
```

This command will remove the `VITAL_env` environment and all its associated packages.

# Launching Jupyter Notebook from the Command Line
## Instructions
1. Open a terminal or command prompt.

2. Activate the `VITAL_env` Conda environment using the following command:
```
conda activate VITAL_env
```

This command will activate the `VITAL_env` environment, ensuring that you are using the correct Python environment for running Jupyter Notebook.

3. Navigate to the directory where you want to create or open your Jupyter Notebook.

4. Run the following command to launch Jupyter Notebook:
```
jupyter notebook
```

This command will start the Jupyter Notebook server and open a new tab or window in your default web browser.

5. In the Jupyter Notebook interface, you can create a new notebook or open an existing notebook by clicking on the respective options.

6. You can now start working with Jupyter Notebook and run the tutorials available in this GitHub repository.

7. To stop the Jupyter Notebook server, go back to the terminal or command prompt where it was launched and press `Ctrl + C`. Confirm by typing `y` and pressing `Enter`.

## License

Copyright 2025 National Technology & Engineering Solutions of Sandia, LLC (NTESS).
Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains certain rights in this software.

This project is licensed under the Apache License, Version 2.0. See the `LICENSE.md` file for details.

