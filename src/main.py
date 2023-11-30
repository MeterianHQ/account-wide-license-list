import requests
import os
import argparse
import re
import sys
import csv
import time

access_token = os.environ.get("METERIAN_ACCESS_TOKEN")

headers = {
    "Authorization": f"Token {access_token}"
}

class HelpingParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write(f'error: {message}\n')
        self.print_help()
        sys.stderr.write('\n')
        sys.exit(-1)

class ProjectEntry:
    def __init__(self, uuid, name, branch):
        self.uuid = uuid
        self.name = name
        self.branch = branch
        
class LicenseInformation:
    def __init__(self, licenses_list, component_id, copyright_statement):
        self.licenses_list = licenses_list
        self.component_id = component_id
        self.copyright_statement = copyright_statement
        self.project_uuids_list = []
        
    def add_project_uuid_to_list(self, project_uuid):
        self.project_uuids_list.append(project_uuid)

def main():
    args = validate_user_input()
    
    project_entries = get_account_project_entries(args.tag, args.environment)
    
    id_to_license_map = generate_license_information(project_entries, args.environment)
    
    generate_report(project_entries, id_to_license_map, args.name)
    
def validate_user_input():
    parser = HelpingParser(description='will generate a report that will list the licenses of all components given a meterian account')
    parser.add_argument('-t', '--tag', type=str, help='filter projects by tag')
    parser.add_argument('-n', '--name', type=str, help='name the csv file', default='report.csv')
    parser.add_argument('-e', '--environment', type=str, help='subdomain for the meterian api', default='www')

    args = parser.parse_args()

    return args

def get_account_project_entries(filter_tag, meterian_api):
    reports_api = f"https://{meterian_api}.meterian.com/api/v1/reports"
    
    reports_api_response = requests.get(reports_api, headers=headers)
    
    project_entries = reports_api_response.json()
    project_entries = filter_projects_by_tag(filter_tag, project_entries)

    project_uuid_to_project_entry_map = create_project_entries_map(project_entries)
    
    return project_uuid_to_project_entry_map
    
def filter_projects_by_tag(filter_tag, project_entries):
    if filter_tag is not None:
        filtered_project_entries = []
        
        for project_entry in project_entries:
            tags = str(project_entry.get("tags"))
            if re.search(filter_tag, tags):
                filtered_project_entries.append(project_entry)
                
        if not filtered_project_entries:
            print(f"No items with the specified tag '{filter_tag}' found")
            sys.exit(1)
            
        return filtered_project_entries #returns filtered_project_entries when there is a filter_tag
    
    return project_entries #returns project_entries when there is no filter_tag

def create_project_entries_map(project_entries):
    project_uuid_to_project_entry_map = {}
    for entry in project_entries:
        if entry.get('uuid') in project_uuid_to_project_entry_map:
            continue
        
        project_entry = ProjectEntry(
            entry.get('uuid'),
            entry.get('name'),
            entry.get('branch'))
        
        project_uuid_to_project_entry_map[project_entry.uuid] = project_entry

    return project_uuid_to_project_entry_map        

def generate_license_information(project_entries, meterian_api):
    component_id_to_license_information_map = {}
    
    for uuid, project_entry in project_entries.items():
        bible = get_bible(project_entry, meterian_api)
        
        component_ids_list = []
        
        extract_license_information(bible, component_id_to_license_information_map, component_ids_list)
        
        add_project_uuid_to_license_information_map(project_entry.uuid, component_id_to_license_information_map, component_ids_list)
        
    return component_id_to_license_information_map
        
def get_bible(project_entry, meterian_api):
    bibles_api = f"https://{meterian_api}.meterian.com/api/v1/reports/{project_entry.uuid}/bible"
    
    response = requests.post(bibles_api, headers=headers)
    generation_id = response.content.decode()
    
    print(f"generating bible for project {project_entry.name}...")
    while True:
        generation_percentage = get_generation_percentage(generation_id, bibles_api)
        print(f"{generation_percentage}%")
        
        if generation_percentage == 100:
            bibles_api_get_response = requests.get(bibles_api, headers=headers)
            bible = bibles_api_get_response.json()
            return bible
        
        time.sleep(10)
    
def get_generation_percentage(generation_id, bibles_api):
    percentage_api = f"{bibles_api}/{generation_id}"
    
    percentage_response = requests.get(percentage_api, headers=headers)
    
    generation_percentage = percentage_response.json()
    
    return generation_percentage

def extract_license_information(bible, component_id_to_license_information_map, component_ids_list):
    for language, components in bible['components'].items():
        for component in components:
            component_id = f"{language}:{component['name']}:{component['version']}"
            if component_id in component_id_to_license_information_map:
                continue
            
            component_ids_list.append(component_id)
            
            if component.get('copyright'):
                copyright_statement = component.get('copyright').get('text').replace('\n', '')
            else:
                copyright_statement = ''
                
            
            licenses_list = component.get('licenses', [])
            
            licence_information = LicenseInformation(licenses_list, component_id, copyright_statement)
            component_id_to_license_information_map[component_id] = licence_information
            
def add_project_uuid_to_license_information_map(project_entry_uuid, component_id_to_license_information_map, component_ids_list):
    for component_id in component_ids_list:
        component_id_to_license_information_map[component_id].add_project_uuid_to_list(project_entry_uuid)
        
def generate_report(project_entries, id_to_license_map, filename):
    create_report_template(filename)
    
    for component_id, license_information in id_to_license_map.items():
        project_names_and_branches = ""
        for project_uuid in id_to_license_map[component_id].project_uuids_list:
            project_names_and_branches += f"{project_entries[project_uuid].name}:{project_entries[project_uuid].branch};"
        project_names_and_branches = project_names_and_branches[:-1]
        write_to_report(component_id, id_to_license_map, project_names_and_branches, filename)
            
def create_report_template(filename):
    report_headers = [
        "LICENSES", "COMPONENT", "COPYRIGHT STATEMENTS", "PROJECTS"
    ]
    
    with open(filename, mode="w", newline='') as report:
        write = csv.writer(report)
        write.writerow(report_headers)
        
def write_to_report(component_id, id_to_license_map, project_names_and_branch_list, filename):
    with open(filename, mode='a', newline='') as report:
        writer = csv.writer(report)
        writer.writerow([
            id_to_license_map[component_id].licenses_list,
            component_id,
            id_to_license_map[component_id].copyright_statement,
            project_names_and_branch_list
        ])
        
if __name__ == "__main__":
    main()