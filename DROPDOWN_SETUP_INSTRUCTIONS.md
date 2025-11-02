# Excel Dropdown Setup Instructions

## Important: How to See Dropdowns Work

**Excel dropdowns (data validation) only work when you open the file in the Microsoft Excel desktop application**, not in web browsers or Excel Online.

### To See the Dropdown:

1. **Download the Excel file** to your computer
2. **Open it in Microsoft Excel** (not in a web browser)
3. Click on any cell in the **Status column (Column K)**
4. You should see a **small dropdown arrow** appear
5. Click the arrow to see the options: **Ongoing** and **Completed**

## Scripts Available

### 1. Generate New Template with Dropdown
```bash
cd backend
python scripts/generate_ojt_template_with_dropdown.py [output_filename.xlsx]
```

**Example:**
```bash
python scripts/generate_ojt_template_with_dropdown.py ojt_template.xlsx
```

**Output:** A new Excel file with:
- Headers matching your OJT template
- Status column (K) has dropdown with "Ongoing" and "Completed"
- Sample data included

### 2. Add Dropdown to Existing File
```bash
cd backend
python scripts/add_dropdown_to_existing_excel.py <input_file.xlsx> [output_file.xlsx]
```

**Example:**
```bash
# Adds dropdown to existing file (creates new file with _with_dropdown suffix)
python scripts/add_dropdown_to_existing_excel.py ojt_students_update_2025-11-02_all_sections.xlsx

# Or specify output filename
python scripts/add_dropdown_to_existing_excel.py input.xlsx output_with_dropdown.xlsx
```

**What it does:**
- Loads your existing Excel file
- Finds the Status column (looks for "Status" header or uses column K)
- Adds dropdown validation to rows 2-1000
- Saves as a new file (doesn't modify original)

## Troubleshooting

### Dropdown Not Showing?

1. **Make sure you're using Excel desktop app**, not web browser
   - Excel Online / Office 365 web version may not show dropdowns properly
   - Download the file and open in Excel desktop application

2. **Check if data validation is enabled:**
   - Go to Data tab → Data Validation
   - You should see validation rules for the Status column

3. **Try clicking directly on a Status cell:**
   - The dropdown arrow only appears when you click on a cell
   - It doesn't show when just hovering

4. **Verify the Status column:**
   - Dropdown is applied to column K (Status)
   - Starts from row 2 (row 1 is header)

### Testing the Dropdown

1. Open the Excel file in Excel desktop app
2. Click on cell K2 (or any cell in Status column)
3. You should see a small arrow in the bottom-right corner of the cell
4. Click the arrow to see options: "Ongoing", "Completed"
5. Try typing something else - Excel should block invalid entries

## File Locations

- **Generated templates:** `backend/ojt_template_with_status_dropdown.xlsx`
- **Scripts:** 
  - `backend/scripts/generate_ojt_template_with_dropdown.py`
  - `backend/scripts/add_dropdown_to_existing_excel.py`

## Notes

- The dropdown uses a hidden helper sheet (`_StatusOptions`) for reliability
- Options are: **Ongoing** and **Completed** only
- Invalid entries are blocked with an error message
- Dropdown is applied to rows 2-1000 (adjust in script if needed)

