from insert_document import insert_document
from parse_pdf import parse_pdf

if __name__ == "__main__":

    # Step 1: Insert the PDF into the database
    insert_document()

    # Step 2: Parse the PDF and extract relevant information
    parse_pdf()