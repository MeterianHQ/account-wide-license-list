# account-wide-license-list
Creates an account wide license list

- Make sure you have `METERIAN_ACCESS_TOKEN_QA` in your environmnet variables. 

- Make sure you have Python 3.8.10 or later installed

- In the terminal enter `pip install -r requirements.txt` to install the required dependencies

To run the script run `python3 src/main.py` whilst. This will create a csv file in your current working directory named `bibles.csv`.

If you wish to give your csv file a different name use the `-n` or `--name` arguments. e.g. `python3 src/main.py -n reports` will create a csv file named `reports.csv`

If you wish to filter by tags you can use the `-t` or `--tag` arguments. e.g. `python3 src/main.py -t external` will filter the bibles by the tag @external.
