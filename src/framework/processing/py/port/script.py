import port.api.props as props
from port.api.commands import (CommandSystemDonate, CommandSystemExit, CommandUIRender)

from datetime import datetime, timezone
import zipfile
#from ddpinspect import instagram

import pandas as pd
import json


# all functions during the donation process are called here

def process(sessionId):
    yield donate(f"{sessionId}-tracking", '[{ "message": "user entered script" }]')

    key = "zip-contents-example"
    meta_data = []
    meta_data.append(("debug", f"{key}: start"))

    # STEP 1: select the file
    data = None
    while True:
        meta_data.append(("debug", f"{key}: prompt file"))
        promptFile = prompt_file("application/zip, text/plain")
        fileResult = yield render_donation_page(promptFile)
        if fileResult.__type__ == 'PayloadString':
            meta_data.append(("debug", f"{key}: extracting file"))
            extractionResult = doSomethingWithTheFile(fileResult.value)
            if extractionResult != 'invalid':
                meta_data.append(("debug", f"{key}: extraction successful, go to consent form"))
                data = extractionResult
                break
            else:
                meta_data.append(("debug", f"{key}: prompt confirmation to retry file selection"))
                retry_result = yield render_donation_page(retry_confirmation())
                if retry_result.__type__ == 'PayloadTrue':
                    meta_data.append(("debug", f"{key}: skip due to invalid file"))
                    continue
                else:
                    meta_data.append(("debug", f"{key}: retry prompt file"))
                    break

    # STEP 2: ask for consent
    if data is not None:
        meta_data.append(("debug", f"{key}: prompt consent"))
        prompt = prompt_consent(data, meta_data)
        consent_result = yield render_donation_page(prompt)
        if consent_result.__type__ == "PayloadJSON":
            meta_data.append(("debug", f"{key}: donate consent data"))
            yield donate(f"{sessionId}-{key}", consent_result.value)

    yield exit(0, "Success")

# render pages used in process

def render_donation_page(body):
    header = props.PropsUIHeader(props.Translatable({
        "en": "Port flow example",
        "nl": "Port voorbeeld flow"
    }))

    page = props.PropsUIPageDonation("Zip", header, body, None)
    return CommandUIRender(page)


def retry_confirmation():
    text = props.Translatable({
        "en": "Unfortunately, we cannot process your file. Continue, if you are sure that you selected the right file. Try again to select a different file.",
        "nl": "Helaas, kunnen we uw bestand niet verwerken. Weet u zeker dat u het juiste bestand heeft gekozen? Ga dan verder. Probeer opnieuw als u een ander bestand wilt kiezen."
    })
    ok = props.Translatable({
        "en": "Try again",
        "nl": "Probeer opnieuw"
    })
    cancel = props.Translatable({
        "en": "Continue",
        "nl": "Verder"
    })
    return props.PropsUIPromptConfirm(text, ok, cancel)


def prompt_file(extensions):
    description = props.Translatable({
        "en": "Please select any zip file stored on your device.",
        "nl": "Selecteer een willekeurige zip file die u heeft opgeslagen op uw apparaat."
    })

    return props.PropsUIPromptFileInput(description, extensions)

#main function to process zip files

def doSomethingWithTheFile(filename): 
    """takes zip folder, extracts relevant json file contents (your_topics, posts_viewed, videos_watched), then extracts & processes relevant information and returns them as dataframes"""

    #your topics
    your_topics_file = extractJsonContentFromZipFolder(filename, "your_topics")
    yourTopics_df = extract_topics_df(your_topics_file)

    #aggregated post views/day
    posts_viewed_file = extractJsonContentFromZipFolder(filename, "posts_viewed")    
    postViewsperDay_df = get_postViewsPerDay(posts_viewed_file)

    #aggregated video views/day
    videos_viewed_file = extractJsonContentFromZipFolder(filename, "videos_watched")   
    videoViewsperDay_df = get_videoViewsPerDay(videos_viewed_file)

    data = [yourTopics_df, postViewsperDay_df, videoViewsperDay_df]

    print(data)

    return data 

#main content of consent page: displays all data in donation

def prompt_consent(data, meta_data):

    your_topics_title = props.Translatable({
        "en": "Your Topics inferred by Instagram",
        "nl": "Inhoud zip bestand"
    })

    posts_viewed_title = props.Translatable({
        "en": "Number of posts viewed each day in the last week",
        "nl": "Inhoud zip bestand"
    })

    videos_watched_title = props.Translatable({
        "en": "Number of videos watched each day in the last week",
        "nl": "Inhoud zip bestand"
    })


    table_list = []

    table = props.PropsUIPromptConsentFormTable("your_topics", your_topics_title, data[0])
    table_list.append(table)

    table = props.PropsUIPromptConsentFormTable("posts_viewed", posts_viewed_title, data[1])
    table_list.append(table)

    table = props.PropsUIPromptConsentFormTable("videos_watched", videos_watched_title, data[2]) 
    table_list.append(table)
    
    return props.PropsUIPromptConsentForm(table_list, [])


# ---
# helper files for extraction

def extractJsonContentFromZipFolder(zip_file_path, pattern):
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        # Get the list of file names in the zip file
        file_names = zip_ref.namelist()
        
        targetdict = {}

        for file_name in file_names:
                if (file_name.endswith('.json')) and (pattern in file_name):
                    # Read the JSON file into a dictionary
                    with zip_ref.open(file_name) as json_file:
                        json_content = json_file.read()
                        data = json.loads(json_content)
                        targetdict[file_name] = data
                    break

                if file_name == file_names[-1]:
                    print(f"File {pattern}.json is not contained")
                    return None

    return targetdict[file_name]

def import_json_toDict(jsonfile):
    """loads json file as dict"""
    f = open(jsonfile)
    json_dict = json.load(f)
    return json_dict

def extract_topics_df(topics_dict):
    """takes the content of your_topics jsonfile, extracts topics and returns them as a dataframe"""
    if topics_dict != None:
        topics_list = [t['string_map_data']['Name']['value'] for t in topics_dict['topics_your_topics']]
        topics_df = pd.DataFrame(topics_list, columns=['your_topics'])
        return topics_df

def epoch_to_date(epoch_timestamp: str | int) -> str: #thanks ddp-inspector/ddpinspect/src/parserlib/stringparse.py
    """
    Convert epoch timestamp to an ISO 8601 string. Assumes UTC. -> UTC +1

    If timestamp cannot be converted raise CannotConvertEpochTimestamp
    """
    try:
        epoch_timestamp = int(epoch_timestamp)
        out = datetime.fromtimestamp(epoch_timestamp, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError, TypeError) as e:
        logger.error("Could not convert epoch time timestamp, %s", e)
        raise CannotConvertEpochTimestamp("Cannot convert epoch timestamp") from e

    out = pd.to_datetime(out)
    return out.date()

    
# probably want to restrict the days to those within the study period?
def get_postViewsPerDay(posts_viewed_dict):
    """takes content of posts_viewed json file and returns dataframe with number of viewed posts/day"""
    timestamps = [t['string_map_data']['Time']['timestamp'] for t in posts_viewed_dict['impressions_history_posts_seen']] # get list with timestamps in epoch format
    dates = [epoch_to_date(t) for t in timestamps] # convert epochs to dates
    postViewedDates_df = pd.DataFrame(dates, columns=['date']) # convert to df
    aggregated_df = postViewedDates_df.groupby(["date"])["date"].size() # count number of rows per day
    return aggregated_df.reset_index(name='postsViewed_count')

# maybe combine results from get_postViewsPerDay and get_videoViewsPerDay in one dataframe? columns:  date | postsViewed_count | videosViewed_count
def get_videoViewsPerDay(videos_watched_dict):
    """takes content of videos_watched json file and returns dataframe with number of viewed posts/day"""
    timestamps = [t['string_map_data']['Time']['timestamp'] for t in videos_watched_dict["impressions_history_videos_watched"]] # get list with timestamps in epoch format
    dates = [epoch_to_date(t) for t in timestamps] # convert epochs to dates
    videosViewedDates_df = pd.DataFrame(dates, columns=['date']) # convert to df
    aggregated_df = videosViewedDates_df.groupby(["date"])["date"].size() # count number of rows per day
    return aggregated_df.reset_index(name='videosViewed_count')


# unedited from PORT, best leave like that :)

def donate(key, json_string):
    return CommandSystemDonate(key, json_string)


def exit(code, info):
    return CommandSystemExit(code, info)
