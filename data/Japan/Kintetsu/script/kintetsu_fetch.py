import requests
from bs4 import BeautifulSoup
import json
import re
import sys
import time
from tqdm import tqdm
from urllib.parse import urlparse, parse_qs

route_dict = {
    "A": "namba_nara",
    "B": "kyoto_kashihara",
    "C": "keihanna",
    "D": "osaka",
    "E": "nagoya",
    "F": "minamiosaka_yoshino",
    "G": "ikoma",
    "H": "tenri",
    "I": "tawaramoto",
    "J": "shigi",
    "K": "yunoyama",
    "L": "suzuka",
    "M": "yamada_toba_shima",
    "N": "domyoji",
    "O": "nagano",
    "P": "gose",
    "Y": "ikomacable",
    "Z": "nishishigicable",
}

def fetch_train_list(route="A", d=0):
    # Base URL patterns
    match route:
        case "A":
            # namba-nara
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-0&d=1&dw={d}"]
            for k in range(1, 23):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-23&d=1&dw={d}")
            for k in range(1, 23):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-{23-k}&d=1&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-0&d=2&dw={d}")
        case "B":
            # kyoto-kashihara
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=360-0&d=1&dw={d}"]
            for k in range(1, 25):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=360-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=361-0&d=1&dw={d}")
            for k in range(1, 16):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=361-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=361-16&d=1&dw={d}")
            for k in range(1, 16):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=361-{16-k}&d=1&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=360-25&d=1&dw={d}")
            for k in range(1, 25):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=360-{25-k}&d=1&dw={d}")
        case "C":
            # keihanna
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-0&d=1&dw={d}"]
            for k in range(1, 7):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-7&d=1&dw={d}")
            for k in range(1, 7):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-{7-k}&d=1&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-0&d=2&dw={d}")
        case "D":
            # osaka
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=356-0&d=1&dw={d}"]
            for k in range(1, 47):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=356-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=356-47&d=1&dw={d}")
            for k in range(1, 47):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=356-{47-k}&d=1&dw={d}")
        case "E":
            # nagoya
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=413-1&d=1&dw={d}"]
            for k in range(2, 44):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=413-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=413-44&d=1&dw={d}")
            for k in range(2, 44):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=413-{45-k}&d=1&dw={d}")
        case "F":
            # minamiosaka-yoshino
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=349-0&d=1&dw={d}"]
            for k in range(1, 27):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=349-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=373-0&d=1&dw={d}")
            for k in range(1, 15):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=373-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=373-15&d=1&dw={d}")
            for k in range(1, 15):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=373-{15-k}&d=1&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=349-27&d=1&dw={d}")
            for k in range(1, 27):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=349-{27-k}&d=1&dw={d}")
        case "G":
            # ikoma
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=357-0&d=1&dw={d}"]
            for k in range(1, 11):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=357-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=357-11&d=1&dw={d}")
            for k in range(1, 11):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=357-{11-k}&d=1&dw={d}")
        case "H":
            # tenri
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=354-0&d=1&dw={d}"]
            for k in range(1, 3):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=354-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=354-3&d=1&dw={d}")
            for k in range(1, 3):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=354-{3-k}&d=1&dw={d}")
        case "I":
            # tawaramoto
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=353-0&d=1&dw={d}"]
            for k in range(1, 7):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=353-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=353-7&d=1&dw={d}")
            for k in range(1, 7):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=353-{7-k}&d=1&dw={d}")
        case "J":
            # shigi
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=358-0&d=1&dw={d}"]
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=358-1&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=358-2&d=1&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=358-1&d=1&dw={d}")
        case "K":
            # yunoyama
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=409-1&d=1&dw={d}"]
            for k in range(2, 10):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=409-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=409-10&d=1&dw={d}")
            for k in range(2, 10):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=409-{11-k}&d=1&dw={d}")
        case "L":
            # suzuka
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=415-1&d=1&dw={d}"]
            for k in range(2, 5):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=415-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=415-5&d=1&dw={d}")
            for k in range(2, 5):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=415-{6-k}&d=1&dw={d}")
        case "M":
            # yamada-toba-shima
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=452-1&d=1&dw={d}"]
            for k in range(2, 14):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=452-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=453-1&d=1&dw={d}")
            for k in range(2, 5):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=453-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=454-1&d=1&dw={d}")
            for k in range(2, 16):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=454-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=454-16&d=1&dw={d}")
            for k in range(2, 16):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=454-{17-k}&d=1&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=453-5&d=1&dw={d}")
            for k in range(2, 5):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=453-{6-k}&d=1&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=452-14&d=1&dw={d}")
            for k in range(2, 14):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=452-{15-k}&d=1&dw={d}")
        case "N":
            # domyoji
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=351-0&d=1&dw={d}"]
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=351-1&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=351-2&d=1&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=351-1&d=1&dw={d}")
        case "O":
            # nagano
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=355-0&d=1&dw={d}"]
            for k in range(1, 7):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=355-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=355-7&d=1&dw={d}")
            for k in range(1, 7):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=355-{7-k}&d=1&dw={d}")
        case "P":
            # gose
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=359-0&d=1&dw={d}"]
            for k in range(1, 3):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=359-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=359-3&d=1&dw={d}")
            for k in range(1, 3):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=359-{3-k}&d=1&dw={d}")
        case "Y":
            # ikoma_cable
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=665-0&d=1&dw={d}"]
            for k in range(1, 4):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=665-{k}&d=2&dw={d}")
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=665-4&d=1&dw={d}")
            for k in range(1, 4):
                urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=665-{4-k}&d=1&dw={d}")
        case "Z":
            # nishishigi_cable
            urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=666-0&d=1&dw={d}"]
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=666-1&d=1&dw={d}")
        # case "-":
        #     # katsuragisan_ropeway (not implemented)
        #     urls = [f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=667-0&d=1&dw={d}"]
        #     urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=667-1&d=1&dw={d}")
        case "all":
            for r in "ABCDEFGHIJKLMNOPYZ":
                fetch_train_list(r, d)
            return

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    master_train_dict = {}

    for url in tqdm(urls, desc="Fetching Stations"):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.encoding = 'shift_jis'
            
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            # --- HYPER-ROBUST EXTRACTION ---
            station_name = "Unknown Station"
            direction_text = "Unknown Direction"

            # Search all <th> and <td> tags for specific keywords
            for cell in soup.find_all(['th', 'td', 'h2', 'h3']):
                text = cell.get_text(strip=True)
                
                # If the cell contains '■' and '駅', it's the station header
                if '■' in text and '駅' in text:
                    station_name = text.replace('■', '').strip()
                
                # If the cell contains '方面' and 'ダイヤ', it's the direction header
                if '方面' in text and 'ダイヤ' in text:
                    direction_text = text.strip()

            # --- Train Extraction ---
            links = soup.find_all('a', href=True)
            station_new_count = 0
            for link in links:
                href = link['href']
                if 'T7?' in href:
                    params = parse_qs(urlparse(href).query)
                    tx = params.get('tx', [None])[0]
                    if tx and tx not in master_train_dict:
                        master_train_dict[tx] = {
                            "tx": tx,
                            "dw": int(params.get('dw', ['1'])[0]),
                            "sf": params.get('sf', [None])[0]
                        }
                        station_new_count += 1
            
            # Final cleaning for terminal display
            station_name = station_name.replace('\xa0', ' ')
            direction_text = direction_text.replace('\xa0', ' ')
            
            tqdm.write(f"\nStation: {station_name}")
            tqdm.write(f"Line/Dir: {direction_text}")
            tqdm.write(f" - Added {station_new_count} new unique trains.")
            
            time.sleep(0.5)

        except Exception as e:
            tqdm.write(f"\nError: {e}")

    final_list = list(master_train_dict.values())
    with open(f'{route_dict[route]}_{d}.json', 'w', encoding='utf-8') as f:
        json.dump(final_list, f, indent=4, ensure_ascii=False)

    print(f"\nSuccess! Station count: {len(urls)}, Total unique trains: {len(final_list)}")

def convert_to_minutes(time_str):
    """
    Converts 'HH:MM' or 'HH：MM' to total minutes (HH*60 + MM).
    Returns the original string if the pattern is not found.
    """
    if not time_str or time_str.strip() == "":
        return time_str
    
    # Matches {hh} : or ： {mm}. Handles spaces and non-breaking spaces.
    match = re.search(r'(\d{1,2})[:：](\d{2})', time_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        return hours * 60 + minutes
    return time_str

def fetch_train_data(route, d):
    # Load the input data
    if route == "all":
        for r in "ABCDEFGHIJKLMNOPYZ":
            fetch_train_data(r, d)
        return
    
    try:
        with open(f'{route_dict[route]}_{d}.json', 'r', encoding='utf-8') as f:
            train_queries = json.load(f)
        print(f"Fetching {route_dict[route]}.")
    except FileNotFoundError:
        print(f"Error: {route_dict[route]}_{d}.json not found.")
        return

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    all_train_details = []

    for entry in tqdm(train_queries, desc="Fetching Train Details"):
        sf = entry.get('sf')
        tx = entry.get('tx')
        dw = entry.get('dw')
        
        url = f"https://eki.kintetsu.co.jp/norikae/T7?sf={sf}&tx={tx}&dw={dw}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'shift_jis'
            
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            # 1. Extract Meta Data
            header_cell = soup.find('td', {'bgcolor': '#FFB334', 'colspan': '3'})
            if not header_cell:
                continue

            header_text = header_cell.get_text(strip=True)
            meta_match = re.search(r'(.*?)\s+(.*?行き.*?)\s+(.*)のダイヤ', header_text)
            
            if meta_match:
                train_type = meta_match.group(1).strip()
                direction = meta_match.group(2).strip()
                date_type = meta_match.group(3).strip()
            else:
                train_type = "Unknown"
                direction = header_text
                date_type = "Unknown"

            # 2. Extract Station Data
            stop_data = []
            rows = soup.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) == 3:
                    station_text = cells[0].get_text(strip=True)
                    if station_text in ["停車駅", ""]:
                        continue
                    
                    # Clean raw text
                    raw_arr = cells[1].get_text(strip=True).replace('\xa0', '')
                    raw_dep = cells[2].get_text(strip=True).replace('\xa0', '')
                    
                    # Convert to minutes if it's a time string
                    stop_data.append({
                        "station": station_text,
                        "arr": convert_to_minutes(raw_arr),
                        "dep": convert_to_minutes(raw_dep)
                    })

            all_train_details.append({
                "type": train_type,
                "dir": direction,
                "date": date_type,
                "route": route,
                "data": stop_data
            })

            time.sleep(0.3)

        except Exception as e:
            tqdm.write(f"Error fetching tx {tx}: {e}")

    # 3. Save the master list to JSON
    with open(f'{route_dict[route]}_{d}_data.json', 'w', encoding='utf-8') as f:
        json.dump(all_train_details, f, indent=4, ensure_ascii=False)

    print(f"\nProcessing complete. Data saved for {len(all_train_details)} trains.")


def stream_json_files(routes):
    suffixes = ["_0", "_1"]
    
    for key in routes:
        base_name = routes[key]
        for suffix in suffixes:
            file_name = f"{base_name}{suffix}_data.json"
            try:
                with open(file_name, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Logic Change: If the file is a list, yield each object individually
                    if isinstance(data, list):
                        for item in data:
                            yield item
                    else:
                        # If the file is just a single object, yield it as is
                        yield data
                        
                    print(f"{file_name},")
            except FileNotFoundError:
                continue

def wrapup(output_filename):
    print("Wrapping json files ...")
    print("Wrapped files:")
    
    with open(f'{output_filename}.json', 'w', encoding='utf-8') as out_file:
        out_file.write("[\n")
        
        gen = stream_json_files(route_dict)
        
        try:
            # Initialize the first item to handle the comma logic
            first_item = next(gen)
            json.dump(first_item, out_file, indent=4, ensure_ascii=False)
            
            # Continue with the rest of the generator
            for item in gen:
                out_file.write(",\n")
                json.dump(item, out_file, indent=4, ensure_ascii=False)
                
        except StopIteration:
            # This handles the case where NO files were found at all
            print("No files found to wrap.", end="")
            
        out_file.write("\n]")
    print(f"\nDone! Saved to {output_filename}.json")

if __name__ == "__main__":
    # weekday
    fetch_train_list(route="all", d=0)
    fetch_train_data(route="all", d=0)
    # weekend / holiday
    fetch_train_list(route="all", d=1)
    fetch_train_data(route="all", d=1)
    # wrapup
    wrapup("all_data")