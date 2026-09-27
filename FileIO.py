import os
import re
import csv
import time
from battery_app.bdf_output import BDF_COLUMNS, write_metadata
from datetime import datetime
from stat import S_IREAD, S_IWUSR

####################### FILE IO ###########################


def _dialogs():
	"""Load GUI dialogs only for legacy interactive file selection."""
	from battery_gui import dialogs

	return dialogs


def get_directory(title = "Choose Directory"):
	return _dialogs().choose_directory(title)

def write_line_csv(filepath, data_dict):

	with open(filepath, 'a', newline = '') as csvfile:
		writer = csv.DictWriter(csvfile, fieldnames = list(data_dict.keys()))
		if os.stat(filepath).st_size == 0:
			writer.writeheader()
		writer.writerow(data_dict)
		
	#read into pandas dataframe - works, quick to code
	#and is likely easy to extend - but one line doesn't really need it - likely quicker ways to do it
	#df = pd.DataFrame(data_dict).T
  
	#save to csv - append, no index, no header
	#df.to_csv(filepath, header=False, mode='a', index=False)

def write_line_txt(filepath, line):
    with open(filepath, 'a') as txtfile:
        txtfile.write(f'{time.time()}: {line}\n')


def start_file(directory, name, extension = '.csv'):
	dt = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
	filename = f'{name} {dt}{extension}'
	
	filepath = os.path.join(directory, filename)
	
	return filepath


def start_bdf_file(directory, institution_code, cell_name, minimum_sequence=0):
    """Return a unique filename using the Battery Data Format convention.

    The sequence number is the cycle number for this institution/cell. It is
    continued across dates so it remains usable as a persistent cycle index.
    """
    date_text = datetime.now().strftime("%Y%m%d")
    institution = _safe_filename_component(institution_code)
    cell = _safe_filename_component(cell_name)
    prefix = f"{institution}__{cell}__{date_text}_"

    sequence = max(
        _next_bdf_sequence(directory, institution, cell),
        int(minimum_sequence) + 1,
    )
    while True:
        filename = f"{prefix}{sequence:03d}.bdf.csv"
        filepath = os.path.join(directory, filename)
        if not os.path.exists(filepath):
            return filepath
        sequence += 1


def bdf_cycle_number(filepath):
    """Return the cycle number encoded by a BDF filename sequence."""
    match = re.search(r"_(\d+)\.bdf\.csv$", os.path.basename(str(filepath)))
    if match is None:
        raise ValueError(f"Not a BDF cycle filename: {filepath}")
    return int(match.group(1))


def latest_bdf_step_count(directory, institution_code, cell_name):
    """Return the highest recorded BDF step count for an institution/cell."""
    if not os.path.isdir(directory):
        return 0
    institution = _safe_filename_component(institution_code)
    cell = _safe_filename_component(cell_name)
    pattern = re.compile(
        rf"^{re.escape(institution)}__{re.escape(cell)}__\d{{8}}_\d+\.bdf\.csv$"
    )
    latest_step_count = 0
    for filename in os.listdir(directory):
        if not pattern.match(filename):
            continue
        filepath = os.path.join(directory, filename)
        try:
            with open(filepath, newline="", encoding="utf-8") as csvfile:
                for row in csv.DictReader(csvfile):
                    try:
                        latest_step_count = max(
                            latest_step_count,
                            int(float(row.get("Step Count / 1", 0) or 0)),
                        )
                    except (TypeError, ValueError):
                        continue
        except (OSError, csv.Error):
            continue
    return latest_step_count


def _next_bdf_sequence(directory, institution, cell):
    """Find the next sequence across all dates for an institution/cell."""
    if not os.path.isdir(directory):
        return 1
    pattern = re.compile(
        rf"^{re.escape(institution)}__{re.escape(cell)}__\d{{8}}_(\d+)\.bdf\.csv$"
    )
    highest_sequence = 0
    for filename in os.listdir(directory):
        match = pattern.match(filename)
        if match is not None:
            highest_sequence = max(highest_sequence, int(match.group(1)))
    return highest_sequence + 1


def _safe_filename_component(value):
    """Make a user-provided value safe and readable in a filename."""
    component = re.sub(r"[^A-Za-z0-9.-]+", "_", str(value).strip())
    return component.strip("._") or "UNKNOWN"

def get_filepath(name = None, mult = False):
	if name == None:
		title = "Select the file"
	else:
		title = name
	return _dialogs().choose_file(title, "CSV files (*.csv)", multiple=mult)

def get_multiple_filepaths(name = None):
	return get_filepath(name = name, mult = True)

def ensure_subdir_exists_dir(filedir, subdir_name):
	candidate_dir = os.path.join(filedir, subdir_name)
	if not os.path.exists(candidate_dir):
		os.makedirs(candidate_dir)
	return candidate_dir
			
def ensure_subdir_exists_file(filepath, subdir_name):
	return ensure_subdir_exists_dir(os.path.dirname(filepath), subdir_name)

def write_data(filepath, data, printout=False, first_line = False):
	data["Log_Timestamp"] = time.time()
	
	if(printout):
		print(data)
	
	write_line_csv(filepath, data)


def write_bdf_data(filepath, data, printout=False):
    """Append one row using the fixed BDF column order."""
    if printout:
        print(data)

    with open(filepath, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=BDF_COLUMNS,
            extrasaction='ignore',
        )
        if os.stat(filepath).st_size == 0:
            writer.writeheader()
        writer.writerow({column: data.get(column) for column in BDF_COLUMNS})


def write_bdf_metadata(filepath, metadata):
    """Write the JSON-LD sidecar paired with a BDF CSV file."""
    return write_metadata(filepath, metadata)
	
def set_read_only(filepath):
	#make the file read-only so we don't lose decimal places if the CSV is opened in excel
	os.chmod(filepath, S_IREAD)

def allow_write(filepath):
	#make the file writable 
	#https://stackoverflow.com/questions/28492685/change-file-to-read-only-mode-in-python
	os.chmod(filepath, S_IWUSR|S_IREAD)
