import pandas as pd
import requests

# ---------------- DOWNLOAD PHISHTANK ----------------
print("Downloading PhishTank...")
phishtank_url = "http://data.phishtank.com/data/online-valid.csv"
phish = pd.read_csv(phishtank_url)

phish = phish[['url']]
phish['label'] = 1  # phishing


# ---------------- DOWNLOAD OPENPHISH ----------------
print("Downloading OpenPhish...")
openphish_url = "https://openphish.com/feed.txt"

response = requests.get(openphish_url)
open_urls = response.text.split("\n")

openphish = pd.DataFrame(open_urls, columns=['url'])
openphish = openphish.dropna()
openphish['label'] = 1


# ---------------- DOWNLOAD TRANCO (LEGIT) ----------------
print("Downloading Tranco...")
tranco_url = "https://tranco-list.eu/top-1m.csv.zip"

tranco = pd.read_csv(tranco_url, compression='zip', header=None)
tranco = tranco.head(10000)  # only top 10k
tranco.columns = ['rank', 'domain']

tranco['url'] = "https://www." + tranco['domain']
tranco = tranco[['url']]
tranco['label'] = 0  # legit


# ---------------- COMBINE ----------------
print("Merging datasets...")

df = pd.concat([phish, openphish, tranco], ignore_index=True)

# Clean
df = df.drop_duplicates()
df = df.dropna()

# Shuffle
df = df.sample(frac=1).reset_index(drop=True)

# Save
df.to_csv("real_dataset.csv", index=False)

print("✅ DONE: real_dataset.csv created")
print("Total rows:", len(df))