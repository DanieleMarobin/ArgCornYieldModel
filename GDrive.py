"""
Installing what it is necessary:
    pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

Project:
    https://console.cloud.google.com/welcome?project=monitor-353019

On the side bar navigation go to
    1) "APIs and Services"
    2) "Enabled APIs and services" and enable Google Drive API
    3) go to Credentials and create OAuth 2.0 Client IDs
    4) download into the the working folder (E:\grains trading\Streamlit\Monitor) 
       client secret .json file (output of "OAuth client created") and rename it 'credentials.json'
    5) run the 'get_credentials' function and authenticate with google
    6) in the working folder (E:\grains trading\Streamlit\Monitor) a 'token.json' file has been created

Sources:
  Official Guide
    https://developers.google.com/drive/api/guides/about-sdk

    https://discuss.streamlit.io/t/google-drive-csv-file-link-to-pandas-dataframe/8057
    https://developers.google.com/drive/api/v2/reference/files/get

  Scope error:
    https://stackoverflow.com/questions/52135293/google-drive-api-the-user-has-not-granted-the-app-error

Files properties:
    https://developers.google.com/drive/api/v3/reference/files


'execute_query'
Best part of all is the Query system to geet files and files information (check the function 'execute_query' and see where it is used).
High-level:
    1) with a query (giving some conditions), you can seach the whole drive and identify which file you want
       Ex: query = "name = 'last_update.csv'" (look for files whose name is 'last_update.csv')

    2) with a list of fields (asking for some outputs), I can get the info for the above selected files
       Ex: fields='files(id, name, mimeType, parents)' --> give id, name, Type, and folders in which the file is contained (parents)


Query Examples:
    https://developers.google.com/drive/api/guides/search-files#examples
"""

import sys;
sys.path.append(r'C:\Streamlit\Monitor\\') 
sys.path.append(r'\\ac-geneva-24\E\grains trading\Streamlit\Monitor\\')

import os
import os.path
from io import BytesIO
import pandas as pd
import pandas._libs.lib as lib
import concurrent.futures
import pickle
import shutil

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload, MediaIoBaseUpload

# Use the below to force reading from the cloud
LOCAL_DIR = r'\\ac-geneva-24\E\grains trading\Streamlit\Monitor\\'
# LOCAL_DIR = r'go to the cloud'

def update_token():    
    token_paths=[]

    token_paths.append(r'\\ac-geneva-24\E\grains trading\Streamlit\Monitor\token.json')
    token_paths.append(r'\\ac-geneva-24\E\grains trading\Streamlit\Monitor\HelloWorlds\token.json')

    # delete the old one
    for tp in token_paths:
        if os.path.exists(tp):
            os.remove(tp)

    service = build_service()

    return True

def distribute_tokens():
    # Source file
    token_path = r'\\ac-geneva-24\E\grains trading\Streamlit\Monitor\HelloWorlds\token.json'

    # Destination files
    if True:
        distribution_paths=[]

        distribution_paths.append(r'\\ac-geneva-24\E\grains trading\Streamlit\Monitor\token.json')

        distribution_paths.append(r'\\ac-geneva-24\E\grains trading\Streamlit\BraSafraCornYieldModel\token.json')
        distribution_paths.append(r'\\ac-geneva-24\E\grains trading\Streamlit\BraSafrinaCornYieldModel\token.json')

        distribution_paths.append(r'\\ac-geneva-24\E\grains trading\Streamlit\PriceModels\token.json')
        distribution_paths.append(r'\\ac-geneva-24\E\grains trading\Streamlit\Seasonals\token.json')
        
        distribution_paths.append(r'\\ac-geneva-24\E\grains trading\Streamlit\TradeFlow\token.json')
        distribution_paths.append(r'\\ac-geneva-24\E\grains trading\Streamlit\TradeRadar\token.json')

    if os.path.exists(token_path):
        for dp in distribution_paths:
            print('Copying to:', dp)
            shutil.copy(token_path, dp)    
    return True

def get_credentials() -> Credentials:
    # If modifying these scopes, delete the file token.json.
    # SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
    SCOPES = ['https://www.googleapis.com/auth/drive']

    creds = None
    check_folders=[r'C:\Monitor\\', r'\\ac-geneva-24\E\grains trading\Streamlit\Monitor\\']
    token_file='token.json'
    cred_file='credentials.json'

    # Finding credentials file
    for folder in check_folders:
        if os.path.exists(folder+cred_file):
            cred_file=folder+cred_file
            print('Found credentials:', cred_file)
            break

    # Finding token file
    for folder in check_folders:
        if os.path.exists(folder+token_file):
            token_file=folder+token_file
            print('Found token:', token_file)
            break

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES) # old
            flow = InstalledAppFlow.from_client_secrets_file(cred_file, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

def build_service(service=None):
    if service is None:
        creds=get_credentials()    
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)

    return service

def empty_trash(service=None):
    try:
        service = build_service(service)
        service.files().emptyTrash().execute()
        print('Trash emptied')
        return True
    except HttpError as error:
        print(f'An error occurred: {error}')
        return False    

def get_GDrive_map_from_id(id='1jSKcuRbEMGDN0nZWpvoNyfl32D-3YFA3', service=None):
    index_df=pd.read_csv(download_file_from_id(id, service=service), index_col='name')
    return index_df['id'].to_dict()

def get_GDrive_map_from_name(name='GDrive_Securities_index.csv',service=None):
    '''
    slow but shows all the steps
    '''
    
    service = build_service(service)
    id=get_file_id_from_name(file_name=name, service=service)

    if id == None:
        print('The global index does not exist')
        return None
    else:
        print(f'Index id: {id}')
        index_df=pd.read_csv(download_file_from_id(id, service=service), index_col='name')
        return index_df['id'].to_dict()

def get_all_files(service=None, pageSize: int=1000):
    '''
    the output 'items':
        - is a list of dictionaries
        - len(items) = number of files

    each dictionary has 2 keys:
        1) 'id'
        2) 'name'

    '''
    
    try:
        service = build_service(service)

        files = []
        page_token = None
        while True:
            response = service.files().list(pageSize=pageSize, fields='nextPageToken, ''files(id, name)',pageToken=page_token).execute()

            files.extend(response.get('files', []))
            page_token = response.get('nextPageToken', None)

            if page_token is None:
                break

        return files

    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print(f'An error occurred: {error}')

def create_GDrive_index_file(folder_to_index= 'Data/Securities', output_file_path='Data/Tests/GDrive_index.csv', max_n_files: int=1000, service=None):
    # folder='Data/Tests'

    service = build_service(service)
    empty_trash(service=service)

    if folder_to_index==None:
        items = get_all_files(service=service, pageSize=max_n_files)
    else:
        items=list_all_files_in_a_folder(folder=folder_to_index, service=service)

    split = output_file_path.split('/')
    output_folder = '/'.join(split[0:-1])
    output_file_name = split[-1]

    id=get_file_id_from_name(output_file_name, service=service) # check if the file already exists

    df=pd.DataFrame(items)
    
    mask=df['name'].duplicated(keep=False)

    if len(df[mask])>0:
        print('Files with the same name:')
        print(df[mask])
    else:
        print('All good')
        print(f'There are: {len(df)} files')

        df=df.set_index('name')
        if id == None:
            save_df(df,folder=output_folder,file_name=output_file_name, service=service)
        else:
            update_df_with_id(df=df,file_id=id, service=service)
    print(f'Created: {output_file_name}')

def print_all_GDrive_files(creds: Credentials=None, max_n_files_to_print: int=1000):
    items = get_all_files(creds=creds, pageSize=max_n_files_to_print)
            
    print('Files:')
    for item in items:
        print(u'{0} ({1})'.format(item['name'], item['id']))

def execute_query(query = "name = 'last_update.csv'",fields='files(id, name, mimeType, parents)', pageSize: int=1000, service=None):

    service = build_service(service)

    fo = []
    page_token = None
    while True:
        response = service.files().list(pageSize=pageSize, q=query,spaces='drive',fields='nextPageToken,'+fields,pageToken=page_token).execute()
        fo.extend(response.get('files', []))
        page_token = response.get('nextPageToken', None)

        if page_token is None:
            break
    return fo

def update_df_with_id(df, file_id,service=None):
    service = build_service(service)

    fh =BytesIO(bytes(df.to_csv(),'ascii'))
    media_body=MediaIoBaseUpload(fh, mimetype='text/csv')
    
    updated_file = service.files().update(fileId=file_id, media_body=media_body).execute()
    print('Done update_df_with_id')

def save_df(df, file_name='test.csv',folder='Data/Tests',service=None):
    service = build_service(service)

    folder_id=get_file_id_from_path(file_path=folder,service=service)

    file_metadata = {
        'name': file_name,
        'parents':[folder_id]
        }

    fh =BytesIO(bytes(df.to_csv(),'ascii'))
    media_body=MediaIoBaseUpload(fh, mimetype='text/csv')

    file = service.files().create(body=file_metadata, media_body=media_body).execute()
    print('Saved',file_name)

def download_file_from_path(file_path, service=None):

    service = build_service(service)

    split = file_path.split('/')
    folders = split[0:-1]
    file_name = split[-1]
    
    # Get file
    fields='files(id, name, mimeType, parents)'
    files_query=f"name = '{file_name}'"
    files = execute_query(service=service, query=files_query, fields=fields)

    files_dict={}
    for f in files:
        files_dict[f['id']]={'name':f['name'],'id':f['id'],'parents':f['parents']}

    # Get folder
    if len(folders)>0:
        folders_query = "trashed = false and mimeType = 'application/vnd.google-apps.folder'"
        folders = execute_query(service=service, query=folders_query, fields=fields)

        folders_dict={}
        for f in folders:
            if 'parents' in f:
                folders_dict[f['id']]={'name':f['name'],'id':f['id'],'parents':f['parents']}

        dict_paths_id={}

        for f in files_dict:
            fo=[files_dict[f]['name']]
            dict_paths_id['/'.join(get_parent(id=files_dict[f]['parents'][0],folders_dict=folders_dict,fo=fo))]=f
                
        return download_file_from_id(file_id= dict_paths_id[file_path], service=service)
    
    else:
        # At the moment it only gets the first one
        return download_file_from_id(file_id= files[0]['id'], service=service)



def download_file_from_id(file_id, service=None):
    service = build_service(service)

    request = service.files().get_media(fileId=file_id)
    file = BytesIO()
    downloader = MediaIoBaseDownload(file, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()

    file.seek(0)    
    return file

def get_file_id_from_name(file_name, service=None):
    service = build_service(service)

    fields='files(id, name, mimeType, parents)'

    files_query=query=f"name = '{file_name}'"
    files = execute_query(service=service, query=files_query, fields=fields)

    if len(files)==0:
        print('Cannot find:', file_name)
        return None

    files_dict={}
    for f in files:
        files_dict[f['id']]={'name':f['name'],'id':f['id'],'parents':f['parents']}
    fo=list(files_dict.keys())

    if len(fo)>1:
        print('More than 1 file with the same name', list(files_dict.keys()))
        return None
    else:
        return list(files_dict.keys())[0]

def get_file_id_from_path(file_path,service=None):
    service = build_service(service)

    split = file_path.split('/')
    folders = split[0:-1]
    file_name = split[-1]

    fields='files(id, name, mimeType, parents)'

    files_query=query=f"name = '{file_name}'"
    files = execute_query(service=service, query=files_query, fields=fields)

    files_dict={}
    for f in files:
        files_dict[f['id']]={'name':f['name'],'id':f['id'],'parents':f['parents']}

    folders_query = "trashed = false and mimeType = 'application/vnd.google-apps.folder'"
    folders = execute_query(service=service, query=folders_query, fields=fields)

    folders_dict={}
    for f in folders:
        if 'parents' in f:
            folders_dict[f['id']]={'name':f['name'],'id':f['id'],'parents':f['parents']}

    dict_paths_id={}

    for f in files_dict:
        fo=[files_dict[f]['name']]
        dict_paths_id['/'.join(get_parent(id=files_dict[f]['parents'][0],folders_dict=folders_dict,fo=fo))]=f
            
    file_id= dict_paths_id[file_path]

    return file_id

def list_all_files_in_a_folder(folder='Data/Tests',service=None):
    """
    Change:
        fields='files(id, name, parents, modifiedTime)'

    to get a different set of information
    """

    service = build_service(service)

    folder_id=get_file_id_from_path(file_path=folder, service=service)
    print('folder_id:', folder_id)

    fields='files(id, name)'
    files_query=f"'{folder_id}' in parents"
    files = execute_query(service=service, query=files_query, fields=fields)
    return files


def get_file_with_global_index(file_name, dict_name_id, service=None):
    return pd.read_csv(download_file_from_id(dict_name_id[file_name], service=service))


def get_parent(id,folders_dict,fo):
    if (id in folders_dict) and ('parents' in folders_dict[id]):
        fo.insert(0,folders_dict[id]['name'])
        get_parent(folders_dict[id]['parents'][0],folders_dict,fo)    
    return fo

def read_csv_parallel(donwload_dict, service=None, max_workers=500):
    fo={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results={}
        for i,v in enumerate(donwload_dict['file_path']):
            file_path=donwload_dict['file_path'][i]
            dtype=donwload_dict['dtype'][i] if 'dtype' in donwload_dict else None
            parse_dates=donwload_dict['parse_dates'][i] if 'parse_dates' in donwload_dict else False
            index_col=donwload_dict['index_col'][i] if 'index_col' in donwload_dict else None
            names=donwload_dict['names'][i] if 'names' in donwload_dict else lib.no_default
            header=donwload_dict['header'][i] if 'header' in donwload_dict else 'infer'
            dayfirst=donwload_dict['dayfirst'][i] if 'dayfirst' in donwload_dict else False

            results[file_path] = executor.submit(read_csv, file_path, service, dtype, parse_dates, index_col, names, header, dayfirst)
    
    for file_path, res in results.items():
        fo[file_path]=res.result()

    return fo


def listdir(folder=None, cloud_map_id=None, cloud_map_dict=None, service=None):
    '''
    cloud_folder:
        - folder='Data/Weather' or 'Data/Tests'

    cloud_map_id:
        a. id of the file mapping the selected folder
        b. the above file is {file_name:file_id}

    cloud_map:
        - the file mentioned in point 'b.' above (no need to retrieve it again if we already have it)
    '''
    
    folder = get_path(folder)

    if os.path.exists(folder):
        all_files=os.listdir(folder)

    elif cloud_map_dict is not None:
        all_files=list(cloud_map_dict.keys())

    elif cloud_map_id is not None:
        cloud_map_dict=get_GDrive_map_from_id(cloud_map_id, service=service)
        all_files=list(cloud_map_dict.keys())

    else:
        # Remove the last '/' in case it is there
        if folder[-1]=='/':
            folder=folder[0:-1]

        all_files=list_all_files_in_a_folder(folder=folder, service=service)
        all_files=[f['name'] for f in all_files]
        
    return all_files

def get_path(file_path):
    if file_path is None:
        return ''

    if not os.path.exists(file_path):
        local_path=LOCAL_DIR + file_path

        if os.path.exists(local_path):
            return local_path

    return file_path

def is_cloud_id(file_path):
    return ((len(file_path)==33) and ('.' not in file_path))

def read_csv(file_path, service=None, dtype=None, parse_dates=False, index_col=None, names=lib.no_default, header='infer', dayfirst=False, sep=',', encoding=None):

    file_path=get_path(file_path)

    # If the file doesn't exist on the local drive: go to the cloud
    if not os.path.exists(file_path):
        service = build_service(service)

        if is_cloud_id(file_path):
            # print('Cloud id')
            file_path=download_file_from_id(file_path, service)
        else:
            # print('Cloud path')
            file_path=download_file_from_path(file_path, service)            
        
    return pd.read_csv(file_path, dtype=dtype,parse_dates=parse_dates,index_col=index_col,names=names,header=header,dayfirst=dayfirst, sep=sep, encoding=encoding)

def deserialize(file_path, service=None):

    file_path=get_path(file_path)

    if not os.path.exists(file_path):
        service = build_service(service)

        file=download_file_from_path(file_path, service=None)

        return pickle.load(file)
    else:
        return pickle.load(open(file_path, "rb"))

if __name__ == "__main__":
    get_credentials()