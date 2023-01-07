# Import libraries
import streamlit as st
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Set layout
st.set_page_config(layout="wide")


# Define functions
@st.cache
def load_geo_data():
    """
    Load geographic data: country name and region
    :param:
    :return:
    """
    country_list_url = "https://raw.githubusercontent.com/lukes/ISO-3166-Countries-with-Regional-Codes/master/all/all.csv"
    df_country = pd.read_csv(country_list_url)
    df_country = df_country[["name", "region"]]
    df_country.columns = ["Country", "Region"]
    country_name_dict = {
        "Viet Nam": "Vietnam",
        "United Kingdom of Great Britain and Northern Ireland": "United Kingdom"
    }
    df_country["Country"].replace(country_name_dict, inplace=True)

    df_country = df_country.fillna("Undefined")
    return df_country


def extract_external_link(cfp_link):
    """

    :param cfp_link:
    :return:
    """
    page = requests.get(cfp_link)
    result = BeautifulSoup(page.content, "html.parser")

    link = result.find(lambda tag: tag.name == "td" and "Link" in tag.text)
    link = link.text.strip()[6:]

    return link


def extract_cfp_link(query):
    """

    :param query:
    :return:
    """
    crawled_tables = pd.read_html(query, extract_links="body")
    if len(crawled_tables) < 6:
        df_filtered = None
        print("No event found!")
    else:
        # Extract the CFP table
        df = crawled_tables[3]

        print(df.shape)

        # Rename columns
        df.columns = ["Event", "When", "Where", "Deadline"]
        df = df[1:]

        # Extract links
        df["Abbreviation"] = df["Event"].apply(lambda x: x[0])
        df["Link"] = df["Event"].apply(lambda x: "http://www.wikicfp.com" + x[1])
        df_filtered = df[["Abbreviation", "Link"]]

        # Drop duplicates
        df_filtered = df_filtered.drop_duplicates()

        # Extract external links
        df_filtered["CFP Link"] = df_filtered["Link"].apply(extract_external_link)
        df_filtered = df_filtered[["Abbreviation", "CFP Link"]]

    return df_filtered


# TO-DO: solve cases where location is university or country code (USA)
def extract_country(location_name):
    """

    :param location_name:
    :return:
    """
    country_name = location_name
    if location_name is not np.NAN:
        if "," in location_name:
            country_name = location_name.split(",")[-1].strip()

        if "Macau" in location_name:
            country_name = "China"

    # Later this should be replaced by a function
    if country_name == "USA":
        country_name = "United States of America"
    elif country_name == "UK":
        country_name = "United Kingdom"

    return country_name


def main_crawler(query):
    # Get all tables
    tables = pd.read_html(query)

    df_cfp = None
    if len(tables) < 5:
        print("No CFP found!")
    else:
        # Extract the CFP table
        df_cfp = tables[2]
        df_cfp.columns = ["Event", "When", "Where", "Deadline"]
        df_cfp = df_cfp[1:]
        df_cfp = df_cfp.drop_duplicates()

    full_name_arr = []
    time_arr = []
    location_arr = []
    deadline_arr = []
    type_arr = []
    # link  # To be added

    event_arr = df_cfp["Event"].unique()

    for event in event_arr:
        df_cfp_filtered = df_cfp[df_cfp["Event"] == event]

        full_name = df_cfp_filtered.iloc[0, 1]
        full_name_arr.append(full_name)

        time_arr.append(df_cfp_filtered.iloc[1, 1])

        location_arr.append(df_cfp_filtered.iloc[1, 2])

        deadline_arr.append(df_cfp_filtered.iloc[1, 3])

        if ("Special Issue" in full_name) or ("Journal" in full_name):
            type_arr.append("Journal")
        elif "Workshop" in full_name:
            type_arr.append("Workshop")
        else:
            type_arr.append("Conference")

    df_cfp_cleaned = pd.DataFrame({
        "Abbreviation": event_arr,
        "Name": full_name_arr,
        "Type": type_arr,
        "Time": time_arr,
        "Location": location_arr,
        "Deadline": deadline_arr
    })

    # Extract start time and end time
    df_cfp_cleaned[['Start Date', 'End Date']] = df_cfp_cleaned['Time'].str.split(' - ', 1, expand=True)

    # Add country name
    df_cfp_cleaned["Country"] = df_cfp_cleaned["Location"].apply(extract_country)
    df_cfp_cleaned = pd.merge(df_cfp_cleaned, df_country, on="Country", how="left")

    # Add links
    df_links = extract_cfp_link(query)
    df_final = pd.merge(df_cfp_cleaned, df_links, on="Abbreviation", how="left")

    # Fill NaNs
    df_final = df_final.fillna("Undefined")

    # Drop duplicates
    df_final = df_final.drop_duplicates(["Name", "Start Date", "End Date", "Deadline"])

    # Sort columns
    df_final = df_final[["Abbreviation", "Name", "Type",
                         "Start Date", "End Date", "Deadline",
                         "Location", "Country", "Region", "CFP Link"
                         ]]  # "Time",, "CFP Link"

    return df_final


# Load data
df_country = load_geo_data()

# Set a title for the page
st.title('WikiCFP: A Wiki for Calls For Papers')

# Add components
# Keyword
keyword_input = st.text_input("Search CFPs: ")

# Event type
# Region
selected_types = st.multiselect('Type: ',
                                ["Conference", "Workshop", "Journal"],
                                default=["Conference", "Workshop", "Journal"]
                                )

# Time
time_input = st.selectbox(
    'Year: ',
    ('2023', '2024', '2023+', 'All')
)

# Region
selected_regions = st.multiselect('Region: ',
                                  ["Asia", "Europe",
                                   "Africa", "Oceania",
                                   "Americas", "Undefined"
                                   ],
                                  default=["Europe", "Americas", "Undefined"]
                                  )

# Search button
if st.button('Search'):

    if "," in keyword_input:
        keyword_arr = keyword_input.split(',')
        keyword_arr = [text.strip().replace(" ", "+") for text in keyword_arr]
        keyword = "%2C+".join(keyword_arr)
    else:
        keyword = keyword_input.strip().replace(" ", "+")

    if time_input == "2023":
        year = "t"
    elif time_input == "2024":
        year = "n"
    elif time_input == "2023+":
        year = "f"
    else:
        year = "a"

    query = "http://www.wikicfp.com/cfp/servlet/tool.search?q={}&year={}".format(keyword, year)

    df = main_crawler(query)

    # Filter region
    rule = df["Region"].isin(selected_regions) & df["Type"].isin(selected_types)
    df_filtered = df[rule]

    st.markdown("""---""")

    if df_filtered is not None:
        # st.dataframe(df_filtered, use_container_width = False)
        st.markdown(df_filtered.to_html(render_links=True), unsafe_allow_html=True)
    else:
        st.text("No event found!")

# else:
#     st.write('Goodbye')
