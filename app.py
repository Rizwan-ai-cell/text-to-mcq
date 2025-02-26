from flask import Flask, request, render_template, send_file
import os
import pdfplumber
import docx
import csv
from werkzeug.utils import secure_filename
import google.generativeai as genai
from fpdf import FPDF
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# Set your API KEY from environment variable
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))

model = genai.GenerativeModel("models/gemini-1.5-pro")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['RESULTS_FOLDER'] = 'results/'
app.config['ALLOWED_EXTENSION'] = {'pdf', 'txt', 'docx'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Custom function to check allowed file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSION']

# Function to extract text from uploaded files
def extract_text_from_file(file_path):
    _, ext = os.path.splitext(file_path)
    if ext.lower() == '.pdf':
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text()
        return text
    elif ext.lower() == '.docx':
        doc = docx.Document(file_path)
        return '\n'.join([paragraph.text for paragraph in doc.paragraphs])
    elif ext.lower() == '.txt':
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    else:
        print(f"Unsupported file type: {ext}")
        return "Unsupported file type."

# Generate MCQs function
def Question_mcqs_generator(input_text, num_question):
    prompt = f"""
    You are a AI Assistant helping the user generate multiple-choice question (MCQs) based on the following
    '{input_text}'
    Please generate {num_question} MCQs from the text. Each question should have:
    - A clear question
    - Four answer option (labeled A, B, C, D)
    - The correct answer clearly indicated
    Format:
    ## MCQ
    Question: [question]
    A) [option A]
    B) [option B]
    C) [option C]
    D) [option D]
    Correct Answer: [correct option]
    """
    
    response = model.generate_content(prompt).text.strip()
    return response

def save_mcqs_to_file(mcqs, filename):
    result_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    with open(result_path, 'w') as f:
        f.write(mcqs)
    return result_path

def create_pdf(mcqs, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.set_auto_page_break(auto=True, margin=15)
    for mcq in mcqs.split("## MCQ"):
        if mcq.strip():
            pdf.multi_cell(0, 10, mcq.strip())
            pdf.ln(5)
    pdf_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    pdf.output(pdf_path)
    return pdf_path

# Route (endpoints)
@app.route("/")
def index():
    return render_template('index.html')

@app.route("/generate", methods=['POST'])
def generate_mcqs():
    if 'file' not in request.files:
        return "No file part", 400  # Bad Request
    
    file = request.files['file']
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Extract text from the uploaded file
        text = extract_text_from_file(file_path)
        
        if text:
            num_question = int(request.form['num_question'])
            mcqs = Question_mcqs_generator(text, num_question)
            
            # Save the generated MCQ to a file
            txt_filename = f"generated_mcqs_{filename.rsplit('.', 1)[0]}.txt"
            pdf_filename = f"generated_mcqs_{filename.rsplit('.', 1)[0]}.pdf"
            save_mcqs_to_file(mcqs, txt_filename)
            create_pdf(mcqs, pdf_filename)
        
            # Display and allow downloading
            return render_template('result.html', mcqs=mcqs, txt_filename=txt_filename, pdf_filename=pdf_filename)
        return "Invalid file format"

@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(app.config["RESULTS_FOLDER"], filename)
    return send_file(file_path, as_attachment=True)

# Main entry point
if __name__ == "__main__":
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    if not os.path.exists(app.config['RESULTS_FOLDER']): 
        os.makedirs(app.config['RESULTS_FOLDER'])
    
    app.run(debug=True)
