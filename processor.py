from __future__ import annotations
import os
import glob
import pd as pd  # type: ignore
import shutil
from bs4 import BeautifulSoup, Tag  # type: ignore
from datetime import datetime, timedelta

# Synonyms Mapping
# Layouts Config
LAYOUTS = {
    ('English', 35): [
        '#', 'File', 'Fabric', 'Ori. Length (mm)', 'Ori. Width (mm)', 'XF', 'YF', 
        'Real Length (mm)', 'Real Width (mm)', 'Total perim. (mm)', 'Cutted perim. (mm)', 
        'Spread height (mm)', 'Spread hardness', 'Rec.', 'Username', 'Date', 'Opened', 
        'Begin', 'End', 'Closed', 'Setup time', 'Cut time', 'Interruption time', 
        'Interv. time', 'Total time', 'Avg cut speed (m/min)', 'Avg percentage of cut speed (%)', 
        'Amount of patterns', 'Cutted patterns', 'Production Order', 'Spread leaves', 'Even', 
        'Total of cutted patterns', 'Amount compl. mod.', 'Prod. pieces'
    ],
    ('Italian', 29): [
        '#', 'File', 'Fabric', 'Ori. Length (mm)', 'Ori. Width (mm)', 'XF', 'YF', 
        'Real Length (mm)', 'Real Width (mm)', 'Total perim. (mm)', 'Cutted perim. (mm)', 
        'Spread height (mm)', 'Spread hardness', 'Rec.', 'Username', 'Date', 'Opened', 
        'Begin', 'End', 'Closed', 'Setup time', 'Cut time', 'Interruption time', 
        'Interv. time', 'Total time', 'Avg cut speed (m/min)', 'Avg percentage of cut speed (%)', 
        'Prod. pieces', 'Cutted pieces'
    ],
    ('English', 29): [
        '#', 'File', 'Fabric', 'Ori. Length (mm)', 'Ori. Width (mm)', 'XF', 'YF', 
        'Real Length (mm)', 'Real Width (mm)', 'Total perim. (mm)', 'Cutted perim. (mm)', 
        'Spread height (mm)', 'Spread hardness', 'Rec.', 'Username', 'Date', 'Opened', 
        'Begin', 'End', 'Closed', 'Setup time', 'Cut time', 'Interruption time', 
        'Interv. time', 'Total time', 'Avg cut speed (m/min)', 'Avg percentage of cut speed (%)', 
        'Amount of patterns', 'Cutted patterns'
    ],
    ('Portuguese', 32): [
        '#', 'File', 'Fabric', 'Ori. Length (mm)', 'Ori. Width (mm)', 'XF', 'YF', 
        'Real Length (mm)', 'Real Width (mm)', 'Total perim. (mm)', 'Spread height (mm)', 
        'Spread hardness', 'Rec.', 'Username', 'Date', 'Opened', 'Begin', 'End', 'Closed', 
        'Setup time', 'Cut time', 'Interruption time', 'Interv. time', 'Total time', 
        'Amount of patterns', 'Cutted patterns', 'Production Order', 'Spread leaves', 'Even', 
        'Total of cutted patterns', 'Amount compl. mod.', 'Prod. pieces'
    ]

}


LANGUAGE_KEYWORDS = {
    'Tempo de setup': 'Portuguese',
    'Tempo di setup': 'Italian',
    'Setup time': 'English',
    'Tiempo de setup': 'Spanish'
}

# Function removed (Using Layout index-based mapping)


def parse_time_to_seconds(time_str):
    if not time_str or time_str == '---':
        return 0
    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            h, m, s = map(int, parts)
            return h * 3600 + m * 60 + s
        return 0
    except:
        return 0

def format_seconds_to_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def get_safe(row_dict: dict[str, list[str]], key: str, default: str = "") -> str:
    lst = row_dict.get(key, [])
    return lst[0] if lst else default

def parse_html_report(file_path: str) -> tuple[list[str], list[dict[str, list[str]]], str]:
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    table = soup.find('table')
    if not isinstance(table, Tag):
        return [], [], "Unknown"
        
    caption = table.find('caption')
    is_cut_report = lambda text: 'Cut report' in text or 'Report di' in text or 'Relatório' in text or 'Rapporto' in text
    if caption and not is_cut_report(caption.get_text()):
        tables = soup.find_all('table')
        for t in tables:
            cap = t.find('caption')
            if cap and is_cut_report(cap.get_text()):
                table = t
                break
                
    if not isinstance(table, Tag):
        return [], [], "Unknown"
                
    thead = table.find('thead')
    if not isinstance(thead, Tag):
        return [], [], "Unknown"
        
    rows = thead.find_all('tr')
    if len(rows) < 2:
        return [], [], "Unknown"
        
    header_row = rows[1] 
    headers = [th.get_text(strip=True) for th in header_row.find_all('th')]

    
    # Language Detection
    detected_lang = "Unknown"
    for h in headers:
        for kw, lang in LANGUAGE_KEYWORDS.items():
            if kw in h:
                detected_lang = lang
                break
        if detected_lang != "Unknown":
            break
            
    # Unit Multipliers (cm -> mm)
    multipliers = [10.0 if '(cm)' in h else 1.0 for h in headers]
    
    tbody = table.find('tbody')  # type: ignore
    if not isinstance(tbody, Tag):
        return headers, [], detected_lang

        
    data_rows = []
    for tr in tbody.find_all('tr'):  # type: ignore
        cells = tr.find_all('td')
        if not cells or len(cells) < 10: 
            continue
        if any(cell.get('colspan') for cell in cells):
            continue
            
        row_data: dict[str, list[str]] = {}
        for i, cell in enumerate(cells):
            if i < len(headers):
                col_name = headers[i]  # type: ignore


                items = []
                current_text = ""
                for content in cell.contents:
                    if getattr(content, 'name', None) == 'br':
                        items.append(current_text.strip())
                        current_text = ""
                    elif isinstance(content, Tag):
                        if getattr(content, 'name', None) == 'ocurrencyDetails':
                            continue
                        current_text += content.get_text()  # type: ignore
                    else:
                        current_text += str(content)
                if current_text.strip():
                    items.append(current_text.strip())
                    
                # Apply unit multiplier for numeric values
                if multipliers[i] == 10.0:  # type: ignore
                    scaled_items = []
                    for it in items:
                        # Clean item of '.' for checks, but keep '.' for float
                        clean_it = it.replace('.', '', 1)
                        if clean_it.isdigit():
                            try:
                                scaled_items.append(str(float(it) * 10))
                            except:
                                scaled_items.append(it)
                        else:
                            scaled_items.append(it)
                    items = scaled_items
                    
                row_data[col_name] = items
        data_rows.append(row_data)
    return headers, data_rows, detected_lang


def split_row(row_data: dict[str, list[str]], filename: str, detected_lang: str = "Unknown", max_height: float = 0, thresholds: dict = {}) -> list[dict]:
    date_list = row_data.get('Date', [])
    opened_list = row_data.get('Opened', [])
    closed_list = row_data.get('Closed', [])
    
    n = max(len(date_list), len(opened_list), len(closed_list))
    
    # Helper to calculate Overlimits
    def calculate_overlimits(row):
        setup_min = parse_time_to_seconds(row.get('Setup time', '00:00:00')) / 60
        interr_min = parse_time_to_seconds(row.get('Interruption time', '00:00:00')) / 60
        interv_min = parse_time_to_seconds(row.get('Interv. time', '00:00:00')) / 60
        
        row['Setup Overlimit'] = 'Yes' if setup_min > thresholds.get('max_setup_minutes', 2) else 'No'
        row['Interruption Overlimit'] = 'Yes' if interr_min > thresholds.get('max_interruption_minutes', 2) else 'No'
        row['Interval Overlimit'] = 'Yes' if interv_min > thresholds.get('max_interval_minutes', 2) else 'No'

    # Helper to calculate Height Range
    def calculate_height_range(row):
        h_str = get_safe(row_data, 'Spread height (mm)', '0')
        try:
            height = float(h_str)
        except:
            height = 0
            
        if max_height > 60:
            if height <= 22: range_val = "Low"
            elif height <= 46: range_val = "Medium"
            elif height <= 58: range_val = "Upper Medium"
            else: range_val = "High"
        else:
            if height <= 16: range_val = "Low"
            elif height <= 33: range_val = "Medium"
            else: range_val = "High"
        row['Height Range'] = range_val

    # Helper for Valid File
    def calculate_valid_file(row):
        perim_cols = ['Cutted perim. (mm)', 'Total perim. (mm)']
        valid = 'Yes'
        for col in perim_cols:
            vals = row_data.get(col, ["0"])
            val_str = vals[0] if vals else "0"
            try:
                val = float(val_str)
                if val == 0:
                    valid = 'No'
                    break
            except:
                valid = 'No'
                break
        row['Valid File'] = valid

    if n <= 1:
        new_row: dict[str, str] = {}
        for k, v in row_data.items():
            new_row[k] = v[0] if v else ""
        new_row['Filename'] = filename
        orig_pieces_str = get_safe(row_data, 'Prod. pieces', '0')
        if orig_pieces_str in ['INV', 'NE']:
            new_row['Prod. pieces'] = orig_pieces_str
        else:
             new_row['Prod. pieces'] = str(int(float(orig_pieces_str))) if orig_pieces_str.replace('.','',1).isdigit() else orig_pieces_str
        total_time_str = new_row.get('Total time', "00:00:00")
        sub_total_sec = parse_time_to_seconds(total_time_str)
        try:
            pieces_float = float(new_row.get('Prod. pieces', '0'))
        except:
            pieces_float = 0
        pcs_per_min = pieces_float / (sub_total_sec / 60) if sub_total_sec > 0 else 0
        new_row['Pieces/min'] = f"{pcs_per_min:.2f}"
        
        # Add new columns
        new_row['Language'] = detected_lang
        uname = get_safe(row_data, 'Username', '')
        new_row['Username2'] = uname.split('(')[0].strip() if '(' in uname else uname.strip()
        calculate_height_range(new_row)
        calculate_overlimits(new_row)
        calculate_valid_file(new_row)
        
        # Add Production Pieces Valid
        try:
            val_clean = str(new_row.get('Prod. pieces', '0')).replace(' ', '')
            new_row['Production Pieces Valid'] = str(int(float(val_clean)))
        except:
            new_row['Production Pieces Valid'] = '0'
        
        return [new_row]
        
    sub_rows = []
    durations = []
    for i in range(n):
        open_val = opened_list[i] if i < len(opened_list) else ""
        close_val = closed_list[i] if i < len(closed_list) else ""
        if close_val == '---' or open_val == '---':
            durations.append(0)
        else:
            open_sec = parse_time_to_seconds(open_val)
            close_sec = parse_time_to_seconds(close_val)
            duration = close_sec - open_sec
            if duration < 0: 
                duration += 24 * 3600
            durations.append(duration)
    total_duration = sum(durations)
    
    orig_pieces_str = get_safe(row_data, 'Prod. pieces', '0')
    total_pieces = 0
    if orig_pieces_str in ['INV', 'NE']:
        total_pieces = 0
    else:
        try:
            total_pieces = int(float(orig_pieces_str))
        except:
            total_pieces = 0
    allocated_pieces = [0] * n
    if total_duration > 0 and total_pieces > 0:
        proportions = [d / total_duration for d in durations]
        allocated_pieces = [round(p * total_pieces) for p in proportions]
        diff = total_pieces - sum(allocated_pieces)
        if diff != 0:
            max_idx = durations.index(max(durations))
            allocated_pieces[max_idx] += diff
            
    setup_sec = parse_time_to_seconds(get_safe(row_data, 'Setup time', '00:00:00'))
    interr_sec = parse_time_to_seconds(get_safe(row_data, 'Interruption time', '00:00:00'))
    interv_sec = parse_time_to_seconds(get_safe(row_data, 'Interv. time', '00:00:00'))
    
    for i in range(n):
        new_row: dict[str, str] = {}
        for k, v in row_data.items():
            if k in ['Date', 'Opened', 'Closed', 'Begin', 'End', 'Username']:
                new_row[k] = v[i] if i < len(v) else (v[0] if v else "")
            else:
                new_row[k] = v[0] if v else ""
        new_row['Filename'] = filename
        orig_id = get_safe(row_data, '#', '')
        new_row['#'] = f"#{orig_id} {new_row.get('Date', '')}"
        
        new_row['Cut time'] = format_seconds_to_time(durations[i])  # type: ignore
        
        if i == n - 1:
            curr_setup = setup_sec
            curr_interr = interr_sec
            curr_interv = interv_sec
            new_row['Setup time'] = get_safe(row_data, 'Setup time', '00:00:00')
            new_row['Interruption time'] = get_safe(row_data, 'Interruption time', '00:00:00')
            new_row['Interv. time'] = get_safe(row_data, 'Interv. time', '00:00:00')
        else:
            curr_setup = 0
            curr_interr = 0
            curr_interv = 0
            new_row['Setup time'] = "00:00:00"
            new_row['Interruption time'] = "00:00:00"
            new_row['Interv. time'] = "00:00:00"
        sub_total_sec = curr_setup + durations[i] + curr_interr + curr_interv  # type: ignore
        new_row['Total time'] = format_seconds_to_time(sub_total_sec)
        if orig_pieces_str in ['INV', 'NE']:
            new_row['Prod. pieces'] = orig_pieces_str
        else:
            new_row['Prod. pieces'] = str(allocated_pieces[i])  # type: ignore
        perim_str = get_safe(row_data, 'Cutted perim. (mm)', '0')
        try:
            perim = float(perim_str)
        except:
            perim = 0
        speed = (perim / 1000) / (sub_total_sec / 60) if sub_total_sec > 0 else 0
        new_row['Avg cut speed (m/min)'] = f"{speed:.2f}"
        try:
            pieces_float = float(new_row.get('Prod. pieces', '0'))
        except:
            pieces_float = 0
        pcs_per_min = pieces_float / (sub_total_sec / 60) if sub_total_sec > 0 else 0
        new_row['Pieces/min'] = f"{pcs_per_min:.2f}"
        
        # Add new columns
        new_row['Language'] = detected_lang
        uname = row_data.get('Username', [""])[i] if i < len(row_data.get('Username', [])) else (row_data.get('Username', [""])[0] if row_data.get('Username') else "")
        new_row['Username2'] = uname.split('(')[0].strip() if '(' in uname else uname.strip()
        calculate_height_range(new_row)
        calculate_overlimits(new_row)
        calculate_valid_file(new_row)
        
        # Add Production Pieces Valid
        try:
            val_clean = str(new_row.get('Prod. pieces', '0')).replace(' ', '')
            new_row['Production Pieces Valid'] = str(int(float(val_clean)))
        except:
            new_row['Production Pieces Valid'] = '0'
        
        sub_rows.append(new_row)
    return sub_rows


def main():
    input_dir = r"C:\Users\henrique.tamaki\OneDrive - Audaces Automacao e Informatica Industrial Ltda\2601 OneTouch\Bravo\Antigravity Bravo\Input"
    output_dir = r"C:\Users\henrique.tamaki\OneDrive - Audaces Automacao e Informatica Industrial Ltda\2601 OneTouch\Bravo\Antigravity Bravo\Output"
    processed_dir = os.path.join(input_dir, "processado")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)
        
    print("--- Configuration Thresholds ---")
    try:
        max_setup = float(input("Enter maximum setup time (minutes) [default 2]: ") or 2)
        max_interr = float(input("Enter maximum interruption time (minutes) [default 2]: ") or 2)
        max_interv = float(input("Enter maximum interval time (minutes) [default 2]: ") or 2)
    except (EOFError, Exception):
        print("[CONTROL] Non-interactive mode or invalid input. Using defaults (2 min).")
        max_setup, max_interr, max_interv = 2.0, 2.0, 2.0
        
    thresholds = {
        'max_setup_minutes': max_setup,
        'max_interruption_minutes': max_interr,
        'max_interval_minutes': max_interv
    }
        
    html_files = glob.glob(os.path.join(input_dir, "*.html"))
    print(f"[CONTROL] Found {len(html_files)} HTML files to process.")
    if not html_files:
        print("[CONTROL] No HTML files in Input.")
        return
        
    groups: dict[tuple[str, int], list[tuple[str, list[dict[str, list[str]]]]]] = {}

    files_to_move: list[str] = []
    
    for file_path in html_files:
        filename = os.path.basename(file_path)
        try:
            headers, rows, detected_lang = parse_html_report(file_path)
            sig = (detected_lang, len(headers))
            if sig not in groups:
                 groups[sig] = []
            groups[sig].append((file_path, rows))
            files_to_move.append(file_path)
        except Exception as e:
            print(f"[CONTROL] ERROR reading file '{filename}': {e}")
            
    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    for sig, file_list in groups.items():
        lang, count = sig
        print(f"[CONTROL] Group {sig}: found {len(file_list)} files.")
        layout_cols: list[str] = LAYOUTS.get(sig, [])

        
        all_group_rows = []
        for file_path, rows in file_list:  # type: ignore

            filename = os.path.basename(file_path)
            if not rows:
                print(f"[CONTROL] WARNING: '{filename}' yielded 0 rows.")
                continue
                
            # Translate keys based on index if Layout available
            translated_rows: list[dict[str, list[str]]] = []
            for r in rows:
                translated_r: dict[str, list[str]] = {}
                for i, (orig_k, val) in enumerate(r.items()):
                     new_k = orig_k
                     if layout_cols and i < len(layout_cols):
                          new_k = list(layout_cols)[i]
                     translated_r[new_k] = val

                translated_rows.append(translated_r)
                
            # Compute Max Height
            max_height = 0
            for r in translated_rows:
                 h_vals = r.get('Spread height (mm)', ["0"])
                 h_str = h_vals[0] if h_vals else "0"
                 try:
                     max_height = max(max_height, float(h_str))
                 except: pass
                 
            for row in translated_rows:
                 all_group_rows.extend(split_row(row, filename, detected_lang=lang, max_height=max_height, thresholds=thresholds))
                 
        if not all_group_rows:
            print(f"[CONTROL] No data for group {sig}")
            continue
            
        df = pd.DataFrame(all_group_rows)
        if layout_cols:
             original_ordered = [c for c in layout_cols if c in df.columns]
             new_cols = [c for c in df.columns if c not in layout_cols]
             df = df[original_ordered + new_cols]
             
        df = df.fillna("0")
        
        def format_excel_decimal(val):
             if isinstance(val, str):
                 if val.replace('.', '', 1).replace('-', '', 1).isdigit() and '.' in val:
                      return val.replace('.', ',')
             elif isinstance(val, float):
                 return f"{val:.4f}".rstrip('0').rstrip('.').replace('.', ',')
             return val
             
        for col in df.columns:
             df[col] = df[col].apply(format_excel_decimal)
             
        output_file = os.path.join(output_dir, f"Report_ajustado_{lang}_cols_{count}_{now_str}.csv")
        df.to_csv(output_file, index=False, encoding='utf-8-sig', sep=';')
        print(f"[CONTROL] Saved group {sig} CSV to {output_file}")
        
    if files_to_move:
         print(f"[CONTROL] Moving {len(files_to_move)} files to processado...")
         for f in files_to_move:
             try: shutil.move(f, os.path.join(processed_dir, os.path.basename(f)))
             except Exception as e: print(f"Error moving {os.path.basename(f)}: {e}")


if __name__ == "__main__":
    main()
