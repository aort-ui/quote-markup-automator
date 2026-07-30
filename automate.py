import fitz  # PyMuPDF
import io
import os
import platform
import streamlit as st

# --- Web App UI Setup ---
st.set_page_config(page_title="Quote Markup Automator", page_icon="📄")
st.title("📄 Quote Markup Automator")
st.write(
    "Upload a distributor quote to instantly apply a 20% margin (/ 0.80) to all"
    " pricing."
)

# --- File Uploader ---
uploaded_file = st.file_uploader(
    "Drag and drop your Quote PDF here", type="pdf"
)

if uploaded_file is not None:
  st.success("File uploaded successfully! Processing...")

  # Read the uploaded PDF directly from memory
  pdf_bytes = uploaded_file.read()
  doc = fitz.open(stream=pdf_bytes, filetype="pdf")

  # Locate the Calibri font
  current_os = platform.system()
  calibri_path = None
  if current_os == "Windows":
    calibri_path = "C:/Windows/Fonts/calibri.ttf"
  elif current_os == "Darwin":
    calibri_path = "/Library/Fonts/Microsoft/Calibri.ttf"

  running_total = 0.0

  for page_num in range(len(doc)):
    page = doc[page_num]

    use_calibri = False
    if calibri_path and os.path.exists(calibri_path):
      page.insert_font(fontname="cali", fontfile=calibri_path)
      use_calibri = True

    target_font = "cali" if use_calibri else "helv"
    words = page.get_text("words")

    # 1. Group words by vertical line (y-coordinate baseline)
    line_dict = {}
    for w in words:
      # Group words within ~4 points vertically
      y_key = round(w[1] / 4.0) * 4.0
      if y_key not in line_dict:
        line_dict[y_key] = []
      line_dict[y_key].append(w)

    # 2. Process each horizontal row on the quote
    for y_key, line_words in line_dict.items():
      # Sort words from left to right
      line_words.sort(key=lambda item: item[0])

      qty_word = None
      price_word = None
      ext_word = None
      total_word = None

      # Identify columns based on horizontal (x) position on the page
      for w in line_words:
        w_text = w[4].strip()
        x0 = w[0]

        # Check for Merchandise / Total line
        if "Merchandise:" in w_text or "Total:" in w_text:
          total_word = w
          continue

        clean = w_text.replace("$", "").replace(",", "")
        try:
          val = float(clean)
          if val <= 0 or val > 500000:
            continue

          # Column bounds based on layout x-coordinates:
          if 300 <= x0 < 370 and qty_word is None:
            qty_word = (int(val), w)
          elif 370 <= x0 < 470 and price_word is None and "." in w_text:
            price_word = (val, w)
          elif 470 <= x0 < 580 and ext_word is None and "." in w_text:
            ext_word = (val, w)
        except ValueError:
          continue

      # --- LINE ITEM RECALCULATION (Qty * New Unit Price) ---
      if qty_word and price_word and ext_word:
        qty = qty_word[0]
        old_unit_price = price_word[0]
        unit_w = price_word[1]
        ext_w = ext_word[1]

        # Calculate new unit price and multiply strictly by quantity
        new_unit_price = round(old_unit_price / 0.80, 2)
        new_ext_price = round(qty * new_unit_price, 2)

        running_total += new_ext_price

        # Redraw Unit Price and Ext Price boxes
        updates = [
            (unit_w, f"${new_unit_price:,.2f}"),
            (ext_w, f"${new_ext_price:,.2f}"),
        ]

        for w, formatted_text in updates:
          rect = fitz.Rect(w[0], w[1], w[2], w[3])

          # Whiteout old text
          whiteout_box = fitz.Rect(
              rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2
          )
          page.draw_rect(whiteout_box, color=(1, 1, 1), fill=(1, 1, 1))

          # Overlay new calculated text
          write_box = fitz.Rect(
              rect.x1 - 100, rect.y1 - 8, rect.x1, rect.y1 + 5
          )
          page.insert_textbox(
              write_box,
              formatted_text,
              fontname=target_font,
              fontsize=6,
              color=(0, 0, 0),
              align=fitz.TEXT_ALIGN_RIGHT,
          )

      # --- TOTAL RECALCULATION ---
      # Update the grand total to match the sum of recalculated line items
      elif total_word or any(
          "Merchandise:" in w[4] or "Total:" in w[4] for w in line_words
      ):
        for w in line_words:
          w_text = w[4].strip()
          clean = w_text.replace("$", "").replace(",", "")
          try:
            val = float(clean)
            if val > 1000 and w[0] >= 450:
              final_total = (
                  running_total if running_total > 0 else round(val / 0.80, 2)
              )
              formatted_text = f"${final_total:,.2f}"

              rect = fitz.Rect(w[0], w[1], w[2], w[3])
              whiteout_box = fitz.Rect(
                  rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2
              )
              page.draw_rect(whiteout_box, color=(1, 1, 1), fill=(1, 1, 1))

              write_box = fitz.Rect(
                  rect.x1 - 100, rect.y1 - 8, rect.x1, rect.y1 + 5
              )
              page.insert_textbox(
                  write_box,
                  formatted_text,
                  fontname=target_font,
                  fontsize=6,
                  color=(0, 0, 0),
                  align=fitz.TEXT_ALIGN_RIGHT,
              )
          except ValueError:
            continue

  # Save the polished PDF to memory
  output_stream = io.BytesIO()
  doc.save(output_stream)
  doc.close()

  # Reset stream position for download
  output_stream.seek(0)

  # --- Download Button ---
  st.write("---")
  st.download_button(
      label="⬇️ Download Marked-Up Quote",
      data=output_stream,
      file_name="Client_Ready_Quote.pdf",
      mime="application/pdf",
      type="primary",
  )
