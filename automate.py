import io
import os
import platform
import fitz  # PyMuPDF
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

  # Locate Calibri font path dynamically per OS
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

    # --- STEP 1: Dynamically Detect Column Headers (Qty, Price, Ext Price) ---
    qty_x, price_x, ext_x = None, None, None
    for w in words:
      text = w[4].strip().lower()
      xc = (w[0] + w[2]) / 2
      if text == "qty" and qty_x is None:
        qty_x = xc
      elif text == "price" and price_x is None and ext_x is None:
        price_x = xc
      elif "ext" in text and ext_x is None:
        ext_x = xc
      elif text == "price" and price_x is not None and ext_x is None:
        ext_x = xc

    # Fallback defaults if headers aren't detected on this page
    if qty_x is None:
      qty_x = 310.0
    if price_x is None:
      price_x = 390.0
    if ext_x is None:
      ext_x = 510.0

    # --- STEP 2: Collect All Price & Qty Candidate Tokens ---
    candidates = []
    for w in words:
      text = w[4].strip()
      clean = text.replace("$", "").replace(",", "")
      xc = (w[0] + w[2]) / 2
      yc = (w[1] + w[3]) / 2

      try:
        val = float(clean)
        if 0 < val <= 500000:
          col_type = None
          if abs(xc - qty_x) < 45 and "." not in text:
            col_type = "qty"
          elif abs(xc - price_x) < 55 and ("." in text or "$" in text):
            col_type = "price"
          elif abs(xc - ext_x) < 65 and ("." in text or "$" in text):
            col_type = "ext"

          if col_type:
            candidates.append(
                {"type": col_type, "val": val, "w": w, "xc": xc, "yc": yc}
            )
      except ValueError:
        continue

    # --- STEP 3: Pass 1 - Pair Line Items Within Vertical Windows ---
    updated_word_ids = set()
    candidates.sort(key=lambda c: c["yc"])  # Sort vertically
    used_indices = set()
    grouped_rows = []

    for i, c in enumerate(candidates):
      if i in used_indices:
        continue

      row = {c["type"]: c}
      used_indices.add(i)

      # Find matching columns within a 22pt vertical window (handles multi-line items)
      for j, c2 in enumerate(candidates):
        if j in used_indices:
          continue
        if abs(c2["yc"] - c["yc"]) <= 22 and c2["type"] not in row:
          row[c2["type"]] = c2
          used_indices.add(j)

      grouped_rows.append(row)

    for r in grouped_rows:
      q_item = r.get("qty")
      p_item = r.get("price")
      e_item = r.get("ext")

      if p_item:
        p_val = p_item["val"]
        p_w = p_item["w"]

        new_unit_price = round(p_val / 0.80, 2)
        updated_word_ids.add(id(p_w))

        # Render new unit price
        w = p_w
        rect = fitz.Rect(w[0], w[1], w[2], w[3])
        page.draw_rect(
            fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2),
            color=(1, 1, 1),
            fill=(1, 1, 1),
        )
        page.insert_textbox(
            fitz.Rect(rect.x1 - 100, rect.y1 - 8, rect.x1, rect.y1 + 5),
            f"${new_unit_price:,.2f}",
            fontname=target_font,
            fontsize=6,
            color=(0, 0, 0),
            align=fitz.TEXT_ALIGN_RIGHT,
        )

        # Extended price calculation
        if q_item:
          q_val = int(q_item["val"])
          new_ext_price = round(q_val * new_unit_price, 2)
        elif e_item:
          new_ext_price = round(e_item["val"] / 0.80, 2)
        else:
          new_ext_price = None

        if e_item and new_ext_price:
          e_w = e_item["w"]
          updated_word_ids.add(id(e_w))
          running_total += new_ext_price

          w = e_w
          rect = fitz.Rect(w[0], w[1], w[2], w[3])
          page.draw_rect(
              fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2),
              color=(1, 1, 1),
              fill=(1, 1, 1),
          )
          page.insert_textbox(
              fitz.Rect(rect.x1 - 100, rect.y1 - 8, rect.x1, rect.y1 + 5),
              f"${new_ext_price:,.2f}",
              fontname=target_font,
              fontsize=6,
              color=(0, 0, 0),
              align=fitz.TEXT_ALIGN_RIGHT,
          )

    # --- STEP 4: Pass 2 - Universal Fallback for Unmatched Prices & Totals ---
    for w in words:
      if id(w) in updated_word_ids:
        continue

      text = w[4].strip()
      clean = text.replace("$", "").replace(",", "")

      try:
        if "." in text or "$" in text:
          val = float(clean)
          if val <= 0 or val > 500000:
            continue

          xc = (w[0] + w[2]) / 2

          # If this is the final total box on the bottom right
          if xc > (ext_x - 60) and val > 1000:
            new_val = (
                running_total if running_total > 0 else round(val / 0.80, 2)
            )
          else:
            new_val = round(val / 0.80, 2)

          formatted_text = f"${new_val:,.2f}"

          rect = fitz.Rect(w[0], w[1], w[2], w[3])
          page.draw_rect(
              fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2),
              color=(1, 1, 1),
              fill=(1, 1, 1),
          )
          page.insert_textbox(
              fitz.Rect(rect.x1 - 100, rect.y1 - 8, rect.x1, rect.y1 + 5),
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
