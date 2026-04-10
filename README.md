# AI-Powered Quiz Web App

This project is a production-ready Streamlit quiz app that:

- parses a syllabus PDF and detects chapters
- extracts PYQ text to mimic exam style
- retrieves only the relevant syllabus chunks for selected chapters
- generates MCQs with Groq using a RAG-style workflow
- runs an interactive quiz with progress tracking, timer support, retry mode, and detailed feedback

## Project Structure

```text
app.py
utils/pdf_parser.py
utils/chunking.py
utils/retriever.py
utils/mcq_generator.py
utils/evaluator.py
utils/cache.py
requirements.txt
README.md
```

## Features

- Streamlit-based UI for upload, quiz, and result flow
- Default PDF support using `Syllabus.pdf` and `SamplePYQs.pdf`
- Automatic chapter detection with manual section fallback
- Chunking into 300-500 word retrieval units
- Chapter-aware retrieval to limit token usage
- Groq-based MCQ generation with strict JSON validation
- JSON + in-memory cache to reduce repeated API calls
- Retry incorrect questions
- Score, percentage, explanations, and answer review

## Setup

1. Create and activate a virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root.

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

`GROQ_MODEL` is optional. The default model is `llama-3.3-70b-versatile`.

## Running the App

Use the following command from the project root:

```bash
streamlit run app.py
```

## How It Works

1. The syllabus PDF is parsed with PyMuPDF.
2. Text is cleaned and grouped into detected chapters or fallback sections.
3. Each chapter is split into 300-500 word chunks.
4. Only the selected chapter chunks are retrieved for generation.
5. PYQ text is compressed into a style reference block.
6. Groq generates MCQs in strict JSON format.
7. The app validates the response before starting the quiz.

## Default PDF Usage

If you keep these files in the project root, the app will use them automatically when no uploads are provided:

- `Syllabus.pdf`
- `SamplePYQs.pdf`

## Deployment on Streamlit Cloud

1. Push this project to GitHub.
2. Open Streamlit Community Cloud.
3. Create a new app and point it to this repository.
4. Set the main file path to `app.py`.
5. In the app settings or secrets, add:

```toml
GROQ_API_KEY="your_groq_api_key_here"
GROQ_MODEL="llama-3.3-70b-versatile"
```

6. Deploy the app.

## Notes

- If a PDF is scanned and contains no extractable text, the app will ask for a text-based PDF.
- The app does not send the full syllabus to the model. It sends only retrieved chapter chunks.
- Generated MCQs are cached using chapter selection, difficulty, question count, and content fingerprints.
