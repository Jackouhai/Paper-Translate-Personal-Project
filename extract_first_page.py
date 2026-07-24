import fitz

input_pdf = "backend/uploads/2606.13668v1.pdf"
output_pdf = "backend/uploads/2606.13668v1_page1.pdf"

src = fitz.open(input_pdf)
dst = fitz.open()

dst.insert_pdf(src, from_page=0, to_page=0)

dst.save(output_pdf)

dst.close()
src.close()

print("Done:", output_pdf)
