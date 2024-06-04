import streamlit as st
import requests
import json
import base64
from PIL import Image, ImageFilter
import fitz  # PyMuPDF
import io
import re

def safe_load_json(validation_arguments):
    try:
        # Replace single quotes with double quotes to make it valid JSON
        valid_json = validation_arguments.replace("'", '"')
        # The JSON loads function expects double backslashes for escape sequences.
        # Replacing single backslashes with double backslashes before JSON parsing to preserve them in regex.
        valid_json = valid_json.replace("\\", "\\\\")
        # Load the JSON string
        data = json.loads(valid_json)
        # Extract the 'pattern' and replace double backslashes with single backslashes for regex usage
        pattern = data['pattern']
        cleaned_pattern = pattern.replace('\\\\', '\\')
        #st.text(cleaned_pattern)
        return cleaned_pattern      
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return ""
    except KeyError as e:
        print(f"Missing key in JSON data: {e}")
        return ""
    
def validate_input(input_value, pattern):
    """Return True if input matches pattern, otherwise False."""
    if pattern and not re.match(pattern, input_value):
        return False
    return True

# Set up error placeholders in the session state when creating inputs



def load_image(image_file):
    """Load an image file."""
    return Image.open(image_file)

def get_document_types():
    """Retrieve all document types from the API."""
    url = "http://edms-demo.epik.live/api/v4/document_types/"
    document_types = []
    next_url = url
    while next_url:
        response = requests.get(next_url, auth=('admin', '1234@BCD'))
        if response.status_code == 200:
            data = response.json()
            document_types.extend(data['results'])
            next_url = data['next']  # Update next_url for the next iteration
        else:
            return []  # Return an empty list if there's an error
    return document_types

def get_metadata_types(doc_type_id):
    """Retrieve metadata types for a specific document type."""
    url = f"http://edms-demo.epik.live/api/v4/document_types/{doc_type_id}/metadata_types/"
    response = requests.get(url, auth=('admin', '1234@BCD'))
    if response.status_code == 200:
        return response.json()['results']
    else:
        return []
def get_cabinets():
    url = "http://edms-demo.epik.live/api/v4/cabinets/"
    response = requests.get(url, auth=('admin', '1234@BCD'))
    if response.status_code == 200:
        return response.json()['results']
    else:
        return []

def get_tags():
    url = "http://edms-demo.epik.live/api/v4/tags/"
    response = requests.get(url, auth=('admin', '1234@BCD'))
    if response.status_code == 200:
        return response.json()['results']
    else:
        return []
    
def save_to_json(file_base64, file_name, doc_type_id, cabinet, tag, metadata_values):
    metadata_list = [{"id": id, "value": value} for id, value in metadata_values.items()]
    data = {
        "file_base64": file_base64,
        "dms_domain": "sagawa.epik.live",
        "file_name": file_name,
        "doctype_id": doc_type_id,
        "cabinet": cabinet,
        "tag": tag,
        "docmeta_data": metadata_list
    }
    with open('data.json', 'w') as json_file:
        json.dump(data, json_file)
        
def save_and_download_json(file_base64, file_name, doc_type_id, cabinet, tag, metadata_values):
    progress_text = st.markdown(" ***Please wait a moment for the data submission process.***")
    progress_bar = st.progress(0)
    save_to_json(file_base64, file_name, doc_type_id, cabinet, tag, metadata_values)
    
    progress_bar.progress(40) 
    with open('data.json', 'rb') as f:
        data = f.read()
    progress_bar.progress(75)
    st.download_button(label="Download JSON", data=data, file_name="data.json", mime="application/json")
    json_data = json.loads(data)
    
    response = send_data_to_api(json_data)
    if response.status_code == 200:
        progress_bar.progress(100)
        progress_text.markdown(" :green[Data submission completed successfully!]")
    else:
        st.error(f"Failed to send data to the API: {response.status_code}")
        progress_bar.progress(0)

def send_data_to_api(json_data):
    """Send JSON data to a specified API endpoint."""
    url = "https://dms.api.epik.live/api/processBase64File"
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, json=json_data, headers=headers)
    return response
def main():
    st.set_page_config(layout="wide", page_title="Document Viewer App")
    st.markdown("<style>.reportview-container .main .block-container{max-width: 90%;}</style>", unsafe_allow_html=True)

    document_types = get_document_types()
    doc_type_options = {doc['label']: doc['id'] for doc in document_types}

    cabinets = get_cabinets()
    cabinet_options = {cab['label']: cab['label'] for cab in cabinets}

    tags = get_tags()
    tag_options = {tag['label']: tag['label'] for tag in tags}

    col_title1, col_title2 = st.columns([1,8])
    with col_title2:
        st.title('Document Viewer App')

    col_empty_1, col_select, col_upload, col_empty_4 = st.columns([1,4,4,1])
    with col_select:
        doc_type = st.selectbox("Choose the document type:", list(doc_type_options.keys()), key='doc_type')
        selected_cabinet = st.selectbox("Choose the document cabinet:", list(cabinet_options.keys()), key='cabinet')
        selected_tag = st.selectbox("Choose the document tag:", list(tag_options.keys()), key='tag')

    with col_upload:
        uploaded_file = st.file_uploader("Upload your document", type=['png', 'jpg', 'jpeg', 'pdf'], key="uploaded_file")

    if uploaded_file:
        # Using the uploaded file's name as a part of each metadata input key to ensure freshness
        file_key = uploaded_file.name + str(uploaded_file.size)

    col1, col2_emt, col3_input_filed = st.columns([7,0.2,2.8])
    with col1:
        if uploaded_file:
            if uploaded_file.type == "application/pdf":
                display_pdf(uploaded_file)
            else:
                display_image(uploaded_file)

    with col3_input_filed:
        if doc_type and uploaded_file:
            
            metadata_types = get_metadata_types(doc_type_options[doc_type])
            metadata_values = {}

            for meta in metadata_types:
                metadata_info = meta['metadata_type']
                label = metadata_info['label']
                required = meta['required']
                input_key = f"meta_{metadata_info['id']}_{uploaded_file.name}"
                
                # Check if there's a lookup list
                if metadata_info.get('lookup'):
                    options = metadata_info['lookup'].split(',')
                    # Use selectbox for lookup values
                    selected_option = st.selectbox(
                        f"{label}{' *' if required else ''}", options, key=input_key
                    )
                    metadata_values[metadata_info['id']] = selected_option
                else:
                    # Regular text input
                    metadata_values[metadata_info['id']] = st.text_input(
                        f"{label}{' *' if required else ''}",
                        key=input_key
                    )

            if st.button("Done and Submit", type="primary"):
                handle_submission(uploaded_file, doc_type_options[doc_type], selected_cabinet, selected_tag, metadata_values)

def display_pdf(uploaded_file):
    try:
        doc = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")
        total_pages = len(doc)
        current_page = st.session_state.get('current_page', 0)

        col_empty_PDF, col1_titlePDF, col2, col3 = st.columns([1,5,2,2])
        with col1_titlePDF:
            st.markdown("#### Preview of the PDF:")

        # Navigation buttons
        with col2:
            if st.button('Previous page', key='prev_page'):
                if current_page > 0:
                    current_page -= 1
                    st.session_state['current_page'] = current_page
            
        with col3:
            if st.button('Next page', key='next_page'):
                if current_page < total_pages - 1:
                    current_page += 1
                    st.session_state['current_page'] = current_page

        # Display current page
        page = doc.load_page(current_page)
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img = img.filter(ImageFilter.SHARPEN)
        st.image(img, caption=f"Page {current_page + 1} of {total_pages}", use_column_width=True)
    except Exception as e:
        st.error(f"Error in PDF processing: {e}")



def display_image(uploaded_file):
    image = load_image(uploaded_file)
    image = image.filter(ImageFilter.SHARPEN)
    st.image(image, caption='Uploaded Image', use_column_width=True)

def handle_submission(uploaded_file, doc_type_id, cabinet, tag, metadata_values):
    metadata_types = get_metadata_types(doc_type_id)
    valid = True
    error_messages = []

    for meta_id, value in metadata_values.items():
        meta_info = next((m for m in metadata_types if m['metadata_type']['id'] == meta_id), None)
        if not meta_info:
            continue

        is_required = meta_info['required']
        validation_info = meta_info['metadata_type'].get('validation_arguments', '')
        pattern = safe_load_json(validation_info) if validation_info else ""

        if is_required and not value.strip():
            error_messages.append(f"Field '{meta_info['metadata_type']['label']}' is required.")
            valid = False
        elif pattern and not validate_input(value, pattern):
            error_messages.append(f"Validation failed for {meta_info['metadata_type']['label']}: {value}")
            valid = False

    if error_messages:
        for msg in error_messages:
            st.error(msg)
    
    if valid:
        file_base64 = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
        file_name = uploaded_file.name
        save_and_download_json(file_base64, file_name, doc_type_id, cabinet, tag, metadata_values)
        st.success("Data saved and submitted successfully!")

if __name__ == "__main__":
    main()
