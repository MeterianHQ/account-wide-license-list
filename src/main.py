import requests
import json
import time
import os
import csv
import re
import argparse

access_token = os.environ.get("METERIAN_ACCESS_TOKEN_QA")
reports_api = "https://qa.meterian.com/api/v1/reports"
polling_interval = 5

headers = {
    "Authorization": f"Token {access_token}"
}

name_to_timestamps = {}
libraries_set = set()
library_to_projects = {}
library_to_copyright = {}
library_to_licenses = {}

def main():
    project_entries, csv_filename = read_through_projects()
    
    read_through_bibles(project_entries)
    
    write_bibles_to_csv(csv_filename)

def read_through_projects():
    target_tag, csv_filename = check_arguments()
    project_entries = projects_get_request(target_tag)
    store_latest_timestamps(project_entries)
    
    return project_entries, csv_filename

def check_arguments():
    target_tag, csv_filename = arguments()

    if csv_filename is None:
        csv_filename = "bibles"
    csv_filename += ".csv"

    create_csv_file(csv_filename)

    return target_tag, csv_filename

def arguments():
    parser = argparse.ArgumentParser(description='generates csv file of bibles from the meterian api')
    parser.add_argument('-t', '--tag', type=str, help='filter projects by tag')
    parser.add_argument('-n', '--name', type=str, help='name the csv file')
    args = parser.parse_args()

    target_tag = args.tag
    csv_filename = args.name
    return target_tag, csv_filename

def create_csv_file(csv_filename):
    csv_headers = [
        "LICENSE", "LIBRARY", "COPYRIGHT", "PROJECTS"
    ]

    with open(csv_filename, mode='w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(csv_headers)

def projects_get_request(target_tag):
    reports_response = requests.get(reports_api, headers=headers)

    if reports_response.status_code == 200:
        reports_data = reports_response.json()
        
        reports_data = tag_search(target_tag, reports_data)
        
        return reports_data
    else:
        print(f"Error: {reports_response.status_code}")
        
def tag_search(target_tag, data):
    if target_tag is not None:
        if target_tag:
            data = [item for item in data if re.search(target_tag, str(item.get("tags")))]
            if not data:
                print(f"No items with the specified tag '{target_tag}' found.")
    return data

def store_latest_timestamps(reports_data):
    for report in reports_data:
        report_name = report.get("name")
        report_timestamp = report.get("timestamp")

        if report_name in name_to_timestamps:
            if report_timestamp > name_to_timestamps[report_name]:
                name_to_timestamps[report_name] = report_timestamp

        else:
            name_to_timestamps[report_name] = report_timestamp
            
def read_through_bibles(project_entries):
    for project_entry in project_entries:
        project_uuid = project_entry["uuid"]
        project_name = project_entry.get("name")
        project_branch = project_entry.get("branch")
        project_timestamp = project_entry.get("timestamp")
        
        if project_timestamp != name_to_timestamps[project_name]:
            continue
        
        bible_get_request(project_uuid, project_name, project_branch)
        
def bible_get_request(report_uuid, report_name, report_branch):
    project_url = f"https://qa.meterian.com/api/v1/reports/{report_uuid}/bible"
    percentage = bible_post_request(report_uuid, report_name, report_branch, project_url)

    if percentage == 100:
        bible_get_response = requests.get(project_url, headers=headers)
        if bible_get_response.status_code == 200:
            bible_data = bible_get_response.json()

            bible_json_to_map(bible_data, report_name, report_branch)
        else:
            print(f"Error, trying to get bible for {report_name}:{report_branch}: {bible_get_response.status_code}")
            
def bible_post_request(project_uuid, project_name, project_branch, project_url):
    project_post_response = requests.post(project_url, headers=headers, data="")

    if project_post_response.status_code == 200:
        id = project_post_response.text
        id_api = f"https://qa.meterian.com/api/v1/reports/{project_uuid}/bible/{id}"
        percentage = check_percentage(id_api, headers, project_name, project_branch)

        if percentage == 100:
            return percentage
    else:
        print(f"Error, trying to get iden for {project_name}:{project_branch}: {project_post_response.status_code}")
        
def check_percentage(id_api, headers, project_name, project_branch):
    current_percentage = 0
    percentage_not_changed_count = 0

    while True:
        id_response = requests.get(id_api, headers=headers)
        if id_response.status_code == 200:
            print(f"{project_name}:{project_branch}:\n\t100%")
            return 100  # Exit the loop for a 200 status

        elif id_response.status_code == 404:
            id_data = json.loads(id_response.text)
            print(f"{project_name}:{project_branch}:\n\t{id_data}%")
            if current_percentage == id_data:
                percentage_not_changed_count += 1
                if percentage_not_changed_count == 6:
                    print(f"Timeout Error, trying to generate {project_name}:{project_branch}: {id_response.status_code}")
                    break

            elif id_data > current_percentage:
                current_percentage = id_data
                percentage_not_changed_count = 0
        else:
            print(f"Error, trying to get percentage for {project_name}: {id_response.status_code}")

        time.sleep(polling_interval)
        
def bible_json_to_map(bible_data, project_name, project_branch):
    project = f"{project_name}:{project_branch}"

    for language, array in bible_data['components'].items():
        for item in array:
            library = f"{language}:{item['name']}:{item['version']}"
            if library not in libraries_set:
                libraries_set.add(library)
                library_to_projects[library] = project
            else:
                library_to_projects[library] += f";{project}"

            copyright = item.get('copyright', {}).get('text', '').replace('\n', '') if 'copyright' in item else ''

            licenses = ', '.join(item.get('licenses', []))

            library_to_copyright[library] = f"{copyright}"
            library_to_licenses[library] = licenses
            
def write_bibles_to_csv(csv_filename):
    for library in libraries_set:
        with open(csv_filename, mode='a', newline='') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([library_to_licenses[library], library, library_to_copyright[library], library_to_projects[library]])
            
if __name__ == "__main__":
    main()