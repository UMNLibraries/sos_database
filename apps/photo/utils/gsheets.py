import os
import pandas as pd

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from django.conf import settings

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def gsheets_login():
  """Shows basic usage of the Sheets API.
  Prints values from a sample spreadsheet.
  """
  CREDENTIALS_JSON = os.path.join(settings.BASE_DIR, 'settings', 'credentials.json')
  TOKEN_PATH = os.path.join(settings.BASE_DIR, 'settings', 'token.json')
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists(TOKEN_PATH):
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          CREDENTIALS_JSON, SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open(TOKEN_PATH, "w") as token:
      token.write(creds.to_json())

  try:
    service = build("sheets", "v4", credentials=creds)

    return service

  except HttpError as err:
    print(err)
    return False


def get_sheet_values(service, sheet_id, sheet_name, column_limit='Z'):

    range_value = f'{sheet_name}!A:{column_limit}'
    # Call the Sheets API
    sheet = service.spreadsheets()
    result = (
        sheet.values()
        .get(spreadsheetId=sheet_id, range=range_value)
        .execute()
    )
    values = result.get("values", [])
    if values:
      return values
    else:
      print("No data found.")
      return


def get_gsheets_df(service, sheet_id, sheet_name):
    '''Read values from the Google Sheets API and then export as pandas dataframe'''
    sheet_values = get_sheet_values(service, sheet_id, sheet_name)

    first_row = sheet_values[0]
    df = pd.DataFrame(sheet_values[1:], columns=first_row)
    return df

