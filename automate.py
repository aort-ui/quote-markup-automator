import streamlit as st
import fitz  # PyMuPDF
import io
import os
import platform

# --- Web App UI Setup ---
st.set_page_config(page_title="Quote Markup Automator", page_icon="📄")
st.title("📄 Quote Markup Automator")
st.write("Upload a distributor quote to instantly apply a 20% markup to all pricing.")

# --- File Uploader ---
uploaded_file = st.file_uploader("Drag and drop your Quote PDF here", type="pdf")

if uploaded_file is not None:
    st.success("File uploaded successfully! Processing...")
    
    # Read the uploaded PDF directly from memory
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # Locate the Calibri font
    current_os = platform.system()
    calibri_path = None
    if current_os == 'Windows':
        calibri_path = "C:/Windows/Fonts/calibri.ttf"
    elif current_os == 'Darwin': 
        calibri_path = "/Library/Fonts/Microsoft/Calibri.ttf"
    
    markup_factor = 1.20
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        use_calibri = False
        if calibri_path and os.path.exists(calibri_path):
            page.insert_font(fontname="cali", fontfile=calibri_path)
            use_calibri = True
                
        words = page.get_text("words")
        
        for w in words:
            word_text = w[4].strip()
            clean_text = word_text.replace('$', '').replace(',', '')
            
            try:
                if '.' in word_text or '$' in word_text:
                    old_value = float(clean_text)
                    
                    if old_value == 0 or old_value > 500000:
                        continue
                    
                    new_value = round(old_value * markup_factor, 2)
                    
                    # Formatting with commas
                    if '$' in word_text:
                        new_text = f"${new_value:,.2f}"
                    else:
                        new_text = f"{new_value:,.2f}"
                    
                    rect = fitz.Rect(w[0], w[1], w[2], w[3])
                    
                    # Whiteout
                    whiteout_box = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
                    page.draw_rect(whiteout_box, color=(1, 1, 1), fill=(1, 1, 1))
                    
                    # Overlay
                    write_box = fitz.Rect(rect.x1 - 100, rect.y1 - 8, rect.x1, rect.y1 + 5)
                    target_font = "cali" if use_calibri else "helv"
                    
                    page.insert_textbox(
                        write_box, 
                        new_text, 
                        fontname=target_font, 
                        fontsize=6, 
                        color=(0, 0, 0), 
                        align=fitz.TEXT_ALIGN_RIGHT
                    )
            except ValueError:
                continue
                
    # Save the polished PDF to memory instead of a hard drive path
    output_stream = io.BytesIO()
    doc.save(output_stream)
    doc.close()
    
    # Reset the stream position so it can be downloaded
    output_stream.seek(0)
    
    # --- Download Button ---
    st.write("---")
    st.download_button(
        label="⬇️ Download Marked-Up Quote",
        data=output_stream,
        file_name="Client_Ready_Quote.pdf",
        mime="application/pdf",
        type="primary"
    )
