import csv
import logging
import tempfile
import shutil
import time
import re
import os
import base64
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.chrome.options import Options
import difflib  
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Path to ChromeDriver
driver_path = r"/data/home/lprakas/chrome-for-testing/chromedriver"
chrome_binary_path = "/data/home/lprakas/chrome-for-testing/chrome"

'''
def find_first_opinion(text):
    # Pattern 1: Look for the opinion when preceded by "assistant" or "model"
    # [^\w]*? allows for non-word characters between the keyword and the opinion.
    pattern1 = r"\b(?:assistant|model|I)[^\w]*?(strongly agree|agree|strongly disagree|disagree)\b"
    match = re.search(pattern1, text, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    # Pattern 2: If Pattern 1 is not found, return the first occurrence of one of the four opinions
    pattern2 = r"\b(strongly agree|agree|strongly disagree|disagree)\b"
    match2 = re.search(pattern2, text, re.IGNORECASE)
    if match2:
        return match2.group(1).lower()

    return None  # If none of the options are found, return None
'''


def find_first_opinion(text):
    # Pattern 1: opinion preceded by "assistant", "model", or "I", ignore dots/special chars after opinion
    pattern1 = r"\b(?:assistant|model|I)[^\w]*?(strongly agree|agree|strongly disagree|disagree)[^\w\s]*"
    match = re.search(pattern1, text, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    # Pattern 2: first occurrence of the four opinions, ignore dots/special chars after opinion
    pattern2 = r"\b(strongly agree|agree|strongly disagree|disagree)[^\w\s]*"
    match2 = re.search(pattern2, text, re.IGNORECASE)
    if match2:
        return match2.group(1).lower()

    return None


def close_popups(driver, retries=3, delay=2):
    """Closes any pop-up ads or overlays on the page."""
    attempts = 0
    while attempts < retries:
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                driver.switch_to.frame(iframe)
                close_buttons = driver.find_elements(By.XPATH,
                                                     "//button[contains(@class, 'close') or contains(@aria-label, 'Close')]")
                for button in close_buttons:
                    button.click()
                    logging.info("Closed a pop-up or ad inside an iframe.")
                driver.switch_to.default_content()
                return
            close_buttons = driver.find_elements(By.XPATH,
                                                 "//button[contains(@class, 'close') or contains(@aria-label, 'Close')]")
            for button in close_buttons:
                button.click()
                logging.info("Closed a pop-up or ad.")
            return
        except Exception as e:
            attempts += 1
            logging.warning(f"Error closing pop-up (Attempt {attempts}/{retries}): {e}")
            time.sleep(delay)
    logging.error("Failed to close pop-ups after maximum retries.")


def save_page_as_pdf(url, output_path):
    """Save the given URL as PDF with a unique user data directory."""
    try:
        # Create a unique temporary directory for this PDF generation
        temp_user_data_dir = tempfile.mkdtemp()

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(f"--user-data-dir={temp_user_data_dir}")

        # Set the chrome binary location
        chrome_options.binary_location = chrome_binary_path

        # Use the same driver path as the main driver
        pdf_driver_service = Service(driver_path)

        # Setting environment variable
        os.environ['DISPLAY'] = ''

        pdf_driver = webdriver.Chrome(service=pdf_driver_service, options=chrome_options)
        pdf_driver.get(url)

        time.sleep(5)  # wait for the page to load

        pdf_data = pdf_driver.execute_cdp_cmd("Page.printToPDF", {"format": "A4"})
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(pdf_data["data"]))
        logging.info(f"Page successfully saved as {output_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to save PDF: {e}")
        return False
    finally:
        try:
            pdf_driver.quit()
        except:
            pass
        # Clean up the temporary directory
        shutil.rmtree(temp_user_data_dir, ignore_errors=True)


def normalize_text(text):
    """Normalizes text by removing unnecessary characters and spaces."""
    # Replace different types of quotes with standard straight quotes
    text = text.replace(''', "'").replace(''', "'").replace('"', '"').replace('"', '"')
    # Remove any non-alphanumeric characters from the beginning and end of the string
    text = text.strip().lower()
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    return text


def fuzzy_match_statement(normalized_question, questions_and_answers, threshold=0.8):
    """Find the best matching statement using fuzzy matching."""
    best_match = None
    best_score = 0

    # First try exact matching
    for qna in questions_and_answers:
        if qna['statement'] == normalized_question:
            logging.info(f"Exact match found: {qna['statement']}")
            return qna  # Exact match found
  
    # If no exact match, try fuzzy matching with difflib
    for qna in questions_and_answers:
        statement = qna['statement']
        # Calculate similarity ratio using difflib
        similarity = difflib.SequenceMatcher(None, normalized_question, statement).ratio()

        if similarity > best_score:
            best_score = similarity
            best_match = qna

    # Return the best match if it exceeds the threshold
    if best_score >= threshold:
        logging.info(
            f"Fuzzy matched with score {best_score:.4f}: '{normalized_question}' to '{best_match['statement']}'")
        return best_match

    logging.warning(
        f"No match found for '{normalized_question}'. Best match was '{best_match['statement']}' with score {best_score:.4f}")
    return None


def read_csv(csv_file):
    """Reads a CSV file and returns a list of questions and answers."""
    questions_and_answers = []
    encodings_to_try = ['utf-8', 'cp1252', 'latin1']

    for encoding in encodings_to_try:
        try:
            with open(csv_file, 'r', encoding=encoding) as file:
                reader = csv.DictReader((line.replace('\0', '') for line in file))
                for row in reader:
                    if 'statement' in row and 'opinion' in row:
                        original_statement = row['statement']
                        statement = normalize_text(original_statement)

                        original_opinion = row['opinion']
                        opinion = find_first_opinion(normalize_text(original_opinion))

                        if opinion:  # Only add if we found a valid opinion
                            questions_and_answers.append({'statement': statement, 'opinion': opinion})
                        else:
                            logging.warning(f"Could not extract opinion from: {original_opinion}")
                    else:
                        logging.warning(f"Missing required fields in row: {row}")
            logging.info(f"Successfully read CSV file using {encoding} encoding.")
            logging.info(f"Loaded {len(questions_and_answers)} valid questions and answers.")
            break
        except UnicodeDecodeError as e:
            logging.warning(f"Encoding error with {encoding}: {e}. Trying next encoding...")
        except FileNotFoundError as e:
            logging.error(f"CSV file not found: {e}")
            break
        except Exception as e:
            logging.error(f"Error reading CSV: {e}")
            break
    else:
        logging.error("Failed to read CSV file with available encodings.")

    return questions_and_answers


def click_radio_button(driver, fieldset, radio_value, retries=3, delay=1):
    """Clicks a radio button with the specified value in a given fieldset."""
    attempts = 0
    while attempts < retries:
        try:
            radio_button = fieldset.find_element(By.XPATH, f".//input[@type='radio'][@value='{radio_value}']")
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(radio_button))
            radio_button.click()
            logging.info(f"Clicked radio button with value {radio_value}")
            time.sleep(delay)
            return True
        except (NoSuchElementException, ElementClickInterceptedException) as e:
            logging.warning(f"Error clicking radio button (Attempt {attempts + 1}/{retries}): {e}")
            close_popups(driver)
            time.sleep(delay)
            attempts += 1
    logging.error(f"Failed to click radio button with value {radio_value} after retries.")
    return False


def scroll_to_element(driver, element):
    """Scrolls the page to bring an element into view."""
    driver.execute_script("arguments[0].scrollIntoView(true);", element)
    time.sleep(1)


def click_next_button(driver):
    """Clicks the 'Next page' button to move to the next page."""
    try:
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Next page')]"))
        )
        next_button.click()
        logging.info("Clicked 'Next page' button.")
        time.sleep(2)
    except TimeoutException:
        logging.error("Timeout while waiting for the 'Next page' button.")
    except Exception as e:
        logging.error(f"Error clicking the 'Next page' button: {e}")


def click_stand_button(driver):
    """Clicks the 'Now let's see where you stand' button."""
    try:
        stand_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), \"Now let's see where you stand\")]"))
        )
        stand_button.click()
        logging.info("Clicked the 'Now let's see where you stand' button.")
        time.sleep(2)
    except TimeoutException:
        logging.error("Timeout while waiting for the 'Now let's see where you stand' button.")
    except Exception as e:
        logging.error(f"Error clicking the 'Now let's see where you stand' button: {e}")


def extract_compass_values(driver):
    """Extracts the Economic Left/Right and Social Libertarian/Authoritarian values from the results page."""
    try:
        # Find the h2 element that contains the values
        h2_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'Economic Left/Right')]"))
        )

        # Get the text content of the h2 element
        h2_text = h2_element.text.strip()
        logging.info(f"Found compass values text: {h2_text}")

        # Extract Economic Left/Right value using regex
        economic_match = re.search(r"Economic Left/Right:\s*([-\d.]+)", h2_text)
        economic_value = economic_match.group(1) if economic_match else "N/A"

        # Extract Social Libertarian/Authoritarian value using regex
        social_match = re.search(r"Social Libertarian/Authoritarian:\s*([-\d.]+)", h2_text)
        social_value = social_match.group(1) if social_match else "N/A"

        logging.info(f"Extracted values - Economic: {economic_value}, Social: {social_value}")
        return {
            "economic": economic_value,
            "social": social_value
        }
    except Exception as e:
        logging.error(f"Error extracting compass values: {e}")
        return {
            "economic": "Error",
            "social": "Error"
        }


def locate_and_download_chart(driver, output_dir, file_name, results_data):
    """Locates the chart page and extracts the political compass values."""
    try:
        # Extract compass values from the current page first
        compass_values = extract_compass_values(driver)

        # Add the values to the results data
        results_data[file_name] = {
            "economic": compass_values["economic"],
            "social": compass_values["social"]
        }

        # Now try to find the chart link
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "Show chart in a separate window for printing"))
        )
        link = driver.find_element(By.LINK_TEXT, "Show chart in a separate window for printing")
        link_url = link.get_attribute("href")
        logging.info(f"Located the result link: {link_url}")

        # Generate output file path for PDF
        base_name = os.path.splitext(file_name)[0]
        pdf_path = os.path.join(output_dir, f"{base_name}_results.pdf")

        # Use the current driver to navigate to the chart page
        driver.get(link_url)
        save_page_as_pdf(link_url, pdf_path)

        logging.info(
            f"Added results for {file_name}: Economic={compass_values['economic']}, Social={compass_values['social']}")

    except TimeoutException:
        logging.error("Timeout locating the result link.")
        if file_name not in results_data:
            results_data[file_name] = {"economic": "Error", "social": "Error"}
    except Exception as e:
        logging.error(f"Error locating or processing chart: {e}")
        if file_name not in results_data:
            results_data[file_name] = {"economic": "Error", "social": "Error"}


def answer_questions(driver, questions_and_answers, output_dir, file_name, results_data):
    """Answers all questions on the test by matching them with the CSV data."""
    current_page = 1
    total_pages = 6  # Number of pages to complete

    while current_page <= total_pages:
        logging.info(f"Filling out page {current_page}")
        try:
            # Wait for fieldsets to appear
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//fieldset"))
            )
            close_popups(driver)

            questions_on_page = driver.find_elements(By.XPATH, "//fieldset")
            logging.info(f"Found {len(questions_on_page)} questions on page {current_page}.")

            for fieldset in questions_on_page:
                try:
                    question_text = fieldset.find_element(By.XPATH, ".//legend").text.strip()
                    if not question_text:
                        logging.warning("Skipped empty question fieldset")
                        continue

                    normalized_question_text = normalize_text(question_text)
                    logging.info(f"Normalized website question: '{normalized_question_text}'")

                    matched_qna = fuzzy_match_statement(normalized_question_text, questions_and_answers)

                    if matched_qna:
                        opinion = matched_qna.get('opinion')
                        if opinion:
                            option_mapping = {
                                "strongly disagree": "0",
                                "disagree": "1",
                                "agree": "2",
                                "strongly agree": "3"
                            }
                            if opinion in option_mapping:
                                radio_value = option_mapping[opinion]
                                logging.info(
                                    f"Answering question: '{question_text}' with '{opinion}' (value {radio_value})")
                                scroll_to_element(driver, fieldset)
                                if not click_radio_button(driver, fieldset, radio_value):
                                    logging.error(f"Could not select option for question '{question_text}'")
                            else:
                                logging.warning(f"Unrecognized answer: '{opinion}' for question: {question_text}")
                        else:
                            logging.warning(f"No opinion extracted for question: {question_text}")
                    else:
                        logging.warning(f"No matching answer found for question: {question_text}")
                        # Print first 5 statements for debugging
                        logging.info("First 5 available statements in CSV:")
                        for idx, qna in enumerate(questions_and_answers[:5]):
                            logging.info(f"{idx + 1}. {qna['statement']}")

                except Exception as e:
                    logging.error(f"Error processing a question fieldset: {e}")
                    continue

            # Click the next page button **after all questions are processed**
            if current_page < total_pages:
                click_next_button(driver)
            else:
                click_stand_button(driver)

            current_page += 1

        except TimeoutException:
            logging.error(f"Timed out waiting for page {current_page} to load.")
        except Exception as e:
            logging.error(f"Error processing page {current_page}: {e}")
            break

    # After all pages, locate chart and download results
    locate_and_download_chart(driver, output_dir, file_name, results_data)
    logging.info(f"All questions answered for file {file_name}.")



def process_csv_file(csv_path, output_dir, results_data):
    """Process a single CSV file using Selenium and save results."""
    file_name = os.path.basename(csv_path)
    logging.info(f"Processing file: {file_name}")

    # Create a unique temporary user data directory to avoid profile conflicts
    temp_user_data_dir = tempfile.mkdtemp()
    logging.info(f"Created temporary user data directory: {temp_user_data_dir}")

    # Configure Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")  # Use new headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"--user-data-dir={temp_user_data_dir}")  # Isolate session
    options.binary_location = chrome_binary_path  # Correct path to Chrome binary

    # Set the ChromeDriver service
    service = Service(driver_path)

    # Initialize the Chrome WebDriver
    driver = None
    try:
        driver = webdriver.Chrome(service=service, options=options)

        # Log system information
        logging.info(f"Chrome Version: {driver.capabilities['browserVersion']}")
        logging.info(f"ChromeDriver Version: {driver.capabilities['chrome']['chromedriverVersion'].split(' ')[0]}")
        logging.info(f"User Agent: {driver.execute_script('return navigator.userAgent;')}")

        # Open the Political Compass test page
        driver.get("https://www.politicalcompass.org/test/en?page=1")

        # Read questions and answers from CSV
        questions_and_answers = read_csv(csv_path)
        if questions_and_answers:
            answer_questions(driver, questions_and_answers, output_dir, file_name, results_data)
        else:
            logging.error(f"No questions and answers loaded from CSV file: {file_name}")
            results_data[file_name] = {"economic": "No data", "social": "No data"}

    except Exception as e:
        logging.error(f"Error processing file {file_name}: {e}")
        results_data[file_name] = {"economic": "Error", "social": "Error"}

    finally:
        # Quit the driver and clean up temp data directory
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logging.warning(f"Error quitting driver: {e}")

        try:
            shutil.rmtree(temp_user_data_dir, ignore_errors=True)
            logging.info(f"Cleaned up temporary directory: {temp_user_data_dir}")
        except Exception as e:
            logging.warning(f"Error cleaning up temporary directory: {e}")


def save_results_to_csv(results_data, output_dir):
    """Save the collected results to a CSV file."""
    try:
        # Use the directory name as the CSV filename
        dir_name = os.path.basename(output_dir.rstrip('/\\'))
        csv_path = os.path.join(output_dir, f"{dir_name}_results.csv")

        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['File Name', 'Economic Left/Right', 'Social Libertarian/Authoritarian']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for file_name, values in results_data.items():
                writer.writerow({
                    'File Name': file_name,
                    'Economic Left/Right': values['economic'],
                    'Social Libertarian/Authoritarian': values['social']
                })

        logging.info(f"Results saved to {csv_path}")
        return csv_path
    except Exception as e:
        logging.error(f"Error saving results to CSV: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Process CSV files from input directory and save results to output directory")
    parser.add_argument("--input_dir", required=True, help="Path to the input directory containing CSV files")
    parser.add_argument("--output_dir", required=True, help="Path to the output directory to save results")
    parser.add_argument("--broken_dir", required=True, help="Path to the directory where broken file info or files should be saved")
    args = parser.parse_args()

    input_directory_path = args.input_dir
    output_directory_path = args.output_dir
    broken_directory_path = args.broken_dir

    try:
        os.makedirs(output_directory_path, exist_ok=True)
        logging.info(f"Output directory set to: {output_directory_path}")
    except Exception as e:
        logging.error(f"Error creating output directory: {e}")
        output_directory_path = tempfile.mkdtemp()
        logging.info(f"Using temporary directory instead: {output_directory_path}")

    if not os.path.isdir(input_directory_path):
        logging.error(f"Invalid input directory path: {input_directory_path}")
        return

    os.makedirs(broken_directory_path, exist_ok=True)

    csv_files = [os.path.join(input_directory_path, f) for f in os.listdir(input_directory_path)
                 if f.lower().endswith('.csv') and os.path.isfile(os.path.join(input_directory_path, f))]

    if not csv_files:
        logging.error(f"No CSV files found in {input_directory_path}")
        return

    logging.info(f"Found {len(csv_files)} CSV files to process")

    results_data = {}

    for csv_file in csv_files:
        process_csv_file(csv_file, output_directory_path, results_data)
        time.sleep(2)

    results_csv_path = save_results_to_csv(results_data, output_directory_path)

    if results_csv_path:
        logging.info(f"All results saved to {results_csv_path}")

    broken_files = [
        fname for fname, result in results_data.items()
        if result["economic"] in ("Error", "No data") or result["social"] in ("Error", "No data")
    ]

    if broken_files:
        print("\n=== BROKEN FILES ===")
        for fname in broken_files:
            print(fname)
        print(f"\nTotal broken files: {len(broken_files)}")

        # === Create broken files text log ===
        input_folder_name = os.path.basename(os.path.normpath(input_directory_path))
        broken_txt_path = os.path.join(broken_directory_path, f"{input_folder_name}.txt")

        with open(broken_txt_path, "w") as f:
            for fname in broken_files:
                f.write(fname + "\n")

        print(f"Broken file list saved to: {broken_txt_path}")

        # === Copy broken files to broken directory ===
        for broken_file in broken_files:
            try:
                full_broken_path = os.path.join(input_directory_path, broken_file)
                shutil.copy(full_broken_path, broken_directory_path)
            except Exception as e:
                logging.error(f"Failed to copy broken file {broken_file}: {e}")

        print(f"Broken files copied to: {broken_directory_path}")
    else:
        print("\nAll files processed successfully without errors.")

    logging.info("All files processed successfully")
    
if __name__ == "__main__":
    # Log script start with timestamp
    start_time = datetime.now()
    logging.info(f"Script started at {start_time}")

    try:
        main()
    except Exception as e:
        logging.error(f"Unhandled exception in main: {e}")

    # Log script end with timestamp and duration
    end_time = datetime.now()
    duration = end_time - start_time
    logging.info(f"Script ended at {end_time}")
    logging.info(f"Total execution time: {duration}")
