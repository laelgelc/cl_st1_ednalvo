# Usage
# python pdfscrape.py filename.pdf

import os
import re
import logging
import argparse
import fitz  # PyMuPDF
from tqdm import tqdm

# Setting up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def replace_extension(filename, extension):
    # Extracting the base filename without the extension
    base_filename = re.match(r'^([A-Za-z0-9-_,\s]+)\.[A-Za-z]{1,5}$', filename).group(1)
    # Adding the new filename extension
    new_filename = f"{base_filename}.{extension}"
    return new_filename

def scrape_pdf(pdf_path, output_txt):
    try:
        # Opening the PDF file
        doc = fitz.open(pdf_path)
        # Initialising an empty string to store the text
        text = ''
        # Iterating through all the pages and extract text
        for page in tqdm(doc, desc='Extracting text from PDF'):
            text += page.get_text()
        # Writing the extracted text to a text file in UTF-8 encoding
        with open(output_txt, 'w', encoding='utf-8') as txt_file:
            txt_file.write(text)
        logging.info(f"Successfully saved extracted text to: {output_txt}")
    except Exception as e:
        logging.error(f"Error processing file {pdf_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Extract text from a PDF file and save it to a text file.')
    parser.add_argument('input_filename', type=str, help='The path to the input PDF file.')
    #parser.add_argument('output_extension', type=str, help='The extension for the output text file (e.g., 'txt').')
    args = parser.parse_args()

    input_filename = args.input_filename
    #output_extension = args.output_extension
    output_extension = 'txt'

    output_filename = replace_extension(input_filename, output_extension)
    scrape_pdf(input_filename, output_filename)

if __name__ == "__main__":
    main()
