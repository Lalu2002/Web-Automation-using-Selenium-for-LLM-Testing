# Web-Automation-using-Selenium-for-LLM-Testing

A robust, headless **Selenium automation tool** built to process and score fine-tuned LLM outputs against the web-based **Political Compass Test (PCT)**.  
Features include **fuzzy matching**, **error handling**, and **structured data extraction** for large-scale bias analysis.

---

## Project Overview and Purpose

This Python framework enables **research into the ideological alignment of Large Language Models (LLMs)** by automating the Political Compass Test (PCT).

It programmatically:
- Submits model-generated opinions.
- Quantifies **political bias scores**.
- Records outputs for reproducibility and large-scale analysis.

**Goal:** Automate thousands of LLM evaluations with minimal manual intervention.

---

## Key Components and Technical Highlights

| **Component** | **Function** | **Technical Highlight** |
|----------------|---------------|--------------------------|
| **Input Files (CSV)** | Takes CSV files containing political statements and LLM responses. | **Fuzzy Matching (`difflib`)** — reliably maps varied responses (e.g., “I strongly agree”) to website radio options. |
| **Automation Engine** | Uses Selenium to simulate user interactions with the test. | **Headless Mode & System Engineering** — uses temporary user data dirs for isolated, stable, non-interactive sessions. |
| **Output Extraction** | Extracts Economic (Left/Right) and Social (Libertarian/Authoritarian) scores. | **Structured Data & Auditability** — saves results to CSV and exports PDF charts for research integration. |
| **Configuration** | CLI interface using `argparse` for flexible paths and reproducibility. | **Reproducible Automation (MLOps)** — clean separation of I/O and batch-friendly execution. |

---

## Setup and Installation

### 1. Conda Environment Setup

Dependencies are managed with **Conda**.

| **Action** | **Command** |
|-------------|-------------|
| Create Environment | `conda env create -f selenium_environment.yml` |
| Activate Environment | `conda activate selenium_environment` |

---

### 2. Chrome and ChromeDriver Installation (Critical Step)

The script requires **Google Chrome** and a **matching ChromeDriver** version.  
The browser and driver **must match exactly**.

Refer to the **`setup_instructions.pdf`** file for the exact sequence of commands (`wget`, `unzip`, `chmod`, etc.) to:
- Download and install Chrome.
- Install ChromeDriver.
- Verify version compatibility.

---

### 3. Edit Paths in the Python Script

Update hard-coded paths in `main.py` to match your local setup.

| **Variable** | **Description** | **Action Required** |
|---------------|----------------|----------------------|
| `driver_path` | Path to ChromeDriver executable. | Update to your local path. |
| `chrome_binary_path` | Path to Chrome binary. | Update to your local path. |
| `input_dir` *(CLI Arg)* | Directory of input CSVs. | Specify at runtime. |
| `output_dir` *(CLI Arg)* | Directory for output CSV/PDF results. | Specify at runtime. |

---

##  Known Issues and Maintenance

| **Issue** | **Description** | **Solution** |
|------------|-----------------|---------------|
| **Driver/Binary Mismatch** | Chrome and ChromeDriver versions differ. | Always verify versions before execution. Follow setup instructions to match binaries. |
| **Website Changes** | If the PCT website updates its structure, locators may break. | Update element locators in `answer_questions()` and `extract_compass_values()`. |
| **Failed Files** | Some CSVs may cause runtime errors or parsing failures. | Problematic files are stored in `--broken_dir`. Inspect logs and retry. |

---

## How to Run the Code

Activate your Conda environment:
```bash
conda activate selenium_environment

python main.py --input_dir /path/to/input_dir --output_dir /path/to/output_dir --broken_dir /path/to/broken_dir


## Use the following comand to know the path of you newly created slenium conda environment

conda info --env 

## Use the exact environment to activate it

conda activate env_name

## 
This project was developed for research purposes as part of the paper:
“A Detailed Factor Analysis for the Political Compass Test: Navigating Ideologies of Large Language Models.”
If you use this code, please cite the paper: https://arxiv.org/html/2506.22493v1#S1

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.


