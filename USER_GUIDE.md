# PaperTranslate User Guide

## Introduction

PaperTranslate is a desktop application that translates English scientific PDF documents into Vietnamese while preserving the original document layout.

The application runs entirely on your computer.

---

# System Requirements

Minimum requirements

* Ubuntu 22.04 or newer
* NVIDIA GPU
* NVIDIA Driver installed
* CUDA environment available

Recommended

* RTX 3060 (12 GB VRAM) or better
* 16 GB RAM or more

---

# Installation

Install the application:

```bash
sudo dpkg -i PaperTranslate_0.1.2_amd64.deb
```

If Ubuntu reports missing dependencies:

```bash
sudo apt -f install
```

Launch the application:

```bash
PaperTranslate
```

or open **PaperTranslate** from the Applications menu.

---

# Using PaperTranslate

## Step 1

Open **Settings**.

---

## Step 2

Start the OCR model.

Wait until the status changes to **Ready**.

---

## Step 3

Return to the Home page.

Upload your PDF document.

---

## Step 4

Click **Start Translation**.

The application will begin parsing the document.

---

# For computers with limited GPU memory

If your GPU cannot run both AI models simultaneously (for example RTX 3060 12 GB):

1. Start the OCR model.
2. Upload the PDF.
3. Click **Start Translation**.
4. Wait until parsing finishes.
5. Return to **Settings**.
6. Stop the OCR model.
7. Start the Translator model.
8. Return to the progress window.
9. Translation will continue automatically.

---

# For computers with sufficient GPU memory

If your GPU has enough VRAM:

1. Start the OCR model.
2. Start the Translator model.
3. Upload the PDF.
4. Click **Start Translation**.
5. Wait for completion.

---

# Download Results

After translation finishes, click one of the available download buttons.

Currently supported:

* HTML
* Markdown

---

# Automatic Model Management

PaperTranslate automatically stops every AI model that it started when the application is closed.

Models started outside PaperTranslate are never modified.

---

# Notes

* The first startup of each AI model may take several minutes.
* Do not close the application while a translation is running.
* Large PDF files require additional processing time.

---

# Troubleshooting

## Translation does not start

Check that the required AI model is running in **Settings**.

---

## Model is still loading

Wait until the status changes to **Ready**.

---

## Application is slow

Large scientific PDFs may require several minutes to process.

This behavior is expected.

---

# Current Version

PaperTranslate v0.1.2
