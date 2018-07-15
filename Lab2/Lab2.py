import json
import pickle
import numpy as np
import pandas as pd
from difflib import SequenceMatcher
from sklearn.svm import SVC, SVR
from sklearn.naive_bayes import GaussianNB
from pandas.tseries.offsets import MonthBegin
from sklearn.linear_model import SGDClassifier, SGDRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.base import clone
from sklearn.metrics import precision_score
from flask import Flask, request, jsonify

flask_app = Flask(__name__)

# region Column Names Enum
CATEGORY = "category"
USER_ID = "userId"
WEEKDAY = "weekday"
WORK_WEEK = "work_week"
MONTH = "month"
DATE = "date"
DAY = "day"
INCOME = "income"
AMOUNT = "amount"
NAME = "name"
CATEGORY_ID = "categoryId"
SUBSCRIPTION = "subscription"
WEEKLY_INCOME = "weekly_income"
MONTHLY_INCOME = "monthly_income"
TOTAL_INCOMES_LAST_WEEK = "total_incomes_last_week"
NUM_OF_INCOMES_LAST_WEEK = "num_of_incomes_last_week"
TOTAL_INCOMES_LAST_MONTH = "total_incomes_last_month"
NUM_OF_INCOMES_LAST_MONTH = "num_of_incomes_last_month"

SAME_NAME_LAST_WEEK = "same_name_last_week"
SAME_NAME_LAST_MONTH = "same_name_last_month"
SAME_CATEGORY_ID_LAST_WEEK = "same_categoryId_last_week"
SAME_CATEGORY_ID_LAST_MONTH = "same_categoryId_last_month"
SAME_AMOUNT_LAST_WEEK = "same_amount_last_week"
SAME_AMOUNT_LAST_MONTH = "same_amount_last_month"
# endregion

users_df = None
transactions_df = None
all_categories = None
models = None


# Original "users.json" had invalid structure, I modified it to be valid
def read_users_and_transactions_files(users_file_path, transactions_file_path):
    global users_df
    global transactions_df

    users_df = pd.read_json(users_file_path)
    transactions_df = pd.read_json(transactions_file_path)
    transactions_df = transactions_df.sort_values(DATE)


# region Part A
def part_a():
    global all_categories
    global transactions_df

    transactions_df[WEEKDAY] = pd.to_datetime(transactions_df[DATE]).apply(lambda x: x.weekday())
    transactions_df[WORK_WEEK] = pd.to_datetime(transactions_df[DATE]).apply(lambda x: x.isocalendar()[1])
    transactions_df[MONTH] = pd.to_datetime(transactions_df[DATE]).apply(lambda x: x.month)
    transactions_df[DAY] = pd.to_datetime(transactions_df[DATE]).apply(lambda x: x.day)
    categories_df = transactions_df[CATEGORY].apply(
        lambda x: pd.Series({k if k.lower() != 'subscription' else 'subscription_cat': 1 for v, k in enumerate(x)})).fillna(0)
    all_categories = list(categories_df.columns)
    transactions_df = pd.concat([transactions_df, categories_df], axis=1)
    transactions_df[INCOME] = transactions_df[AMOUNT] < 0
    additional_features_data = []
    features_for_subscription_label = []

    for index, row in transactions_df.iterrows():
        # Income features:
        last_week_incomes = get_last_n_days_incomes(row, 7)
        last_month_incomes = get_last_n_days_incomes(row, 30)
        total_incomes_last_week = round(-last_week_incomes[AMOUNT].sum(), 2) if not last_week_incomes.empty else 0
        num_of_incomes_last_week = len(last_week_incomes.index)
        total_incomes_last_month = round(-last_month_incomes[AMOUNT].sum(), 2) if not last_month_incomes.empty else 0
        num_of_incomes_last_month = len(last_month_incomes.index)
        # Subscription features - to label only:
        # same_name_last_week = same_attr_past_n_days(row, NAME, 7, lambda a, b: SequenceMatcher(None, a, b).ratio() >= 0.7)
        # same_name_last_month = same_attr_past_n_days(row, NAME, 30, lambda a, b: SequenceMatcher(None, a, b).ratio() >= 0.7)
        same_amount_last_week = same_attr_n_days_ago(row, AMOUNT, 7, lambda a, b: abs(a - b) <= 20)
        same_amount_last_month = same_attr_n_days_ago(row, AMOUNT, 30, lambda a, b: abs(a - b) <= 20)
        same_categoryid_last_week = same_attr_n_days_ago(row, CATEGORY_ID, 7, lambda a, b: a == b)
        same_categoryid_last_month = same_attr_n_days_ago(row, CATEGORY_ID, 30, lambda a, b: a == b)
        # This data will be used in the model:
        additional_features_data.append([total_incomes_last_week,
                                         num_of_incomes_last_week,
                                         total_incomes_last_month,
                                         num_of_incomes_last_month])
        # This data won't be used in the model, only to label the Subscription column:
        features_for_subscription_label.append([same_amount_last_week,
                                                same_amount_last_month,
                                                same_categoryid_last_week,
                                                same_categoryid_last_month])
    additional_features_df = pd.DataFrame(additional_features_data, columns=[TOTAL_INCOMES_LAST_WEEK,
                                                                             NUM_OF_INCOMES_LAST_WEEK,
                                                                             TOTAL_INCOMES_LAST_MONTH,
                                                                             NUM_OF_INCOMES_LAST_MONTH])
    features_for_subscription_label_df = pd.DataFrame(features_for_subscription_label, columns=[SAME_AMOUNT_LAST_WEEK,
                                                                                                SAME_AMOUNT_LAST_MONTH,
                                                                                                SAME_CATEGORY_ID_LAST_WEEK,
                                                                                                SAME_CATEGORY_ID_LAST_MONTH])

    # Calculate Subscription target values:
    all_data_df = pd.concat([transactions_df, additional_features_df], axis=1)
    all_data_df[SUBSCRIPTION] = \
        (features_for_subscription_label_df[SAME_AMOUNT_LAST_WEEK] & features_for_subscription_label_df[SAME_CATEGORY_ID_LAST_WEEK]) | \
        (features_for_subscription_label_df[SAME_AMOUNT_LAST_MONTH] & features_for_subscription_label_df[SAME_CATEGORY_ID_LAST_MONTH])
    # Calculate Income target values:
    user_weekly_income = all_data_df[all_data_df[INCOME]][[USER_ID, WORK_WEEK, AMOUNT]].groupby(by=[USER_ID, WORK_WEEK], as_index=False).sum()
    user_weekly_income.rename(columns={AMOUNT: WEEKLY_INCOME}, inplace=True)
    user_weekly_income[WEEKLY_INCOME] = -user_weekly_income[WEEKLY_INCOME]
    user_monthly_income = all_data_df[all_data_df[INCOME]][[USER_ID, MONTH, AMOUNT]].groupby(by=[USER_ID, MONTH], as_index=False).sum()
    user_monthly_income.rename(columns={AMOUNT: MONTHLY_INCOME}, inplace=True)
    user_monthly_income[MONTHLY_INCOME] = -user_monthly_income[MONTHLY_INCOME]
    all_data_df = all_data_df.merge(user_weekly_income, on=[USER_ID, WORK_WEEK])
    all_data_df = all_data_df.merge(user_monthly_income, on=[USER_ID, MONTH])

    return all_data_df


def get_last_n_days_incomes(row, n):
    if n == 7:
        start_date = row[DATE] - pd.DateOffset(days=int(row[WEEKDAY]))
        end_date = row[DATE]
    else:  # n == 30
        start_date = row[DATE] - MonthBegin()  # pd.DateOffset(months=1, days=int(row[WEEKDAY]))
        end_date = row[DATE]
    last_n_days_incomes = transactions_df[(transactions_df[USER_ID] == row[USER_ID]) &
                                          (transactions_df[INCOME]) &
                                          (transactions_df[DATE] >= start_date) &
                                          (transactions_df[DATE] <= end_date)]
    return last_n_days_incomes


def same_attr_n_days_ago(row, attr, n, compare_func):
    last_n_days_transaction = transactions_df[(transactions_df[USER_ID] == row[USER_ID]) &
                                              (transactions_df[INCOME] == False) &
                                              (transactions_df[DATE] == row[DATE] - pd.DateOffset(days=n))]
    return last_n_days_transaction[attr].apply(lambda x: compare_func(x, row[attr])).any()


# endregion

# region Part B


def part_b(data_df):
    subscription_model = build_subscription_model(data_df)
    users_income_models = build_income_models(data_df)
    models_dict = {"subscription": subscription_model, "incomes": users_income_models}
    pickle.dump(models_dict, open('models', 'wb'))


def build_subscription_model(data_df):
    features_cols = all_categories
    X = data_df[features_cols]
    Y = data_df[SUBSCRIPTION]
    x_train, x_test = np.split(X, [int(0.8 * len(X.index))])
    y_train, y_test = np.split(Y, [int(0.8 * len(Y.index))])

    classification_models = {
        "SVC": SVC(),
        "SGD": SGDClassifier(),
        "Naive Bayes": GaussianNB(),
        "MLP": MLPClassifier(),
        "Decision Tree": DecisionTreeClassifier()}

    # Todo choose a specific model and use it
    for name, model in classification_models.items():
        model.fit(x_train, y_train)
        print "Precision for subscription using", name, precision_score(y_test, model.predict(x_test))
    return model


def build_income_models(data_df):
    features_cols = [WORK_WEEK, MONTH, AMOUNT, INCOME] + [TOTAL_INCOMES_LAST_WEEK, NUM_OF_INCOMES_LAST_WEEK,
                                                          TOTAL_INCOMES_LAST_MONTH, NUM_OF_INCOMES_LAST_MONTH]
    regression_models = {"SVR": SVR(),
                         "SGD": SGDRegressor(),
                         "MLP": MLPRegressor(),
                         "Decision Tree": DecisionTreeRegressor(),
                         "Random Forest": RandomForestRegressor(),
                         "Gradient Boost": GradientBoostingRegressor()}
    user_models = {}
    # ToDo choose a specific model and use it
    for name, model in regression_models.items():
        average_month_mse = 0
        average_week_mse = 0
        for user_id in data_df[USER_ID].unique():
            user_models[user_id] = {}
            user_df = data_df[(data_df[USER_ID] == user_id) & (data_df[INCOME])]
            # Sort from beginning to end of month/week
            X_month = user_df.sort_values(DAY)[features_cols]
            X_week = user_df.sort_values(WEEKDAY)[features_cols]
            Y_month = user_df.sort_values(DAY)[MONTHLY_INCOME]
            Y_week = user_df.sort_values(WEEKDAY)[WEEKLY_INCOME]
            x_train_month, x_test_month = np.split(X_month, [int(0.8 * len(X_month.index))])
            x_train_week, x_test_week = np.split(X_week, [int(0.8 * len(X_week.index))])
            y_month_train, y_month_test = np.split(Y_month, [int(0.8 * len(Y_month.index))])
            y_week_train, y_week_test = np.split(Y_week, [int(0.8 * len(Y_week.index))])

            # Month
            month_model = clone(model)
            month_model.fit(x_train_month, y_month_train)
            average_month_mse += mean_squared_error(y_month_test, month_model.predict(x_test_month)) ** 0.5
            print "User ID:", user_id, "monthly using", name, "Mean Error:", mean_squared_error(y_month_test,
                                                                                                month_model.predict(x_test_month)) ** 0.5
            user_models[user_id]['monthly'] = month_model
            # Week
            week_model = clone(model)
            week_model.fit(x_train_week, y_week_train)
            average_week_mse += mean_squared_error(y_week_test, week_model.predict(x_test_week)) ** 0.5
            print "User ID:", user_id, "weekly using", name, "Mean Error:", mean_squared_error(y_week_test, week_model.predict(x_test_week)) ** 0.5
            user_models[user_id]['weekly'] = week_model
        # print "Monthly avg MSE using", name, ":", average_month_mse / len(data_df[USER_ID].unique())
        # print "Weekly avg MSE using", name, ":", average_week_mse / len(data_df[USER_ID].unique())
    return user_models


# endregion

# region Part C
def part_c():
    flask_app.run()


@flask_app.before_first_request
def load_files():
    global all_categories, models, transactions_df
    transactions_df = pd.read_csv('data.csv')
    transactions_df[DATE] = pd.to_datetime(transactions_df[DATE])
    all_categories = [u'Bicycles', u'Shops', u'Food and Drink', u'Restaurants', u'Car Service', u'Ride Share', u'Travel',
                      u'Airlines and Aviation Services', u'Coffee Shop', u'Gyms and Fitness Centers', u'Recreation', u'Deposit', u'Transfer',
                      u'Credit Card', u'Payment', u'Credit', u'Discount Stores', u'Service', u'Telecommunication Services', u'Music, Video and DVD',
                      u'Financial', u'Computers and Electronics', u'Video Games', u'Warehouses and Wholesale Stores', u'Debit', u'Digital Purchase',
                      u'Supermarkets and Groceries', u'Cable', u'Gas Stations', u'Department Stores', u'Bank Fees', u'Overdraft', u'Interest',
                      u'Interest Charged', u'Wire Transfer', 'subscription_cat', u'Personal Care', u'ATM', u'Withdrawal', u'Pharmacies']
    models = pickle.load(open('models', 'rb'))


@flask_app.route('/', methods=['POST'])
def get_predictions():
    try:
        data = json.loads(request.data)
        assert 'trans' in data, "Missing transaction"
        return jsonify(predict(data))
    except Exception as e:
        return repr(e), 500


def predict(data):
    transaction = ready_transaction_to_model(data)
    # ToDo use relevant columns for each model:
    income_features_cols = [WORK_WEEK, MONTH, AMOUNT, INCOME] + [TOTAL_INCOMES_LAST_WEEK, NUM_OF_INCOMES_LAST_WEEK,
                                                                 TOTAL_INCOMES_LAST_MONTH, NUM_OF_INCOMES_LAST_MONTH]
    sub_features_cols = all_categories
    return {
        "subscription": bool(models['subscription'].predict(transaction[sub_features_cols])[0]),
        "weeklyIncome": float(models['incomes'][transaction[USER_ID][0]]['weekly'].predict(transaction[income_features_cols])[0]),
        "monthlyIncome": float(models['incomes'][transaction[USER_ID][0]]['monthly'].predict(transaction[income_features_cols])[0])
    }


def ready_transaction_to_model(data):
    trans_df = pd.DataFrame.from_dict(data).transpose().reset_index().drop('index', axis=1)

    # Turn categories array to discrete (add all categories and fill with 0/1)
    for category in all_categories:
        trans_df[category] = 1 if category in trans_df[CATEGORY][0] else 0
    # Add columns : Weekday, Work Week & Month
    trans_df[DATE] = pd.to_datetime(trans_df[DATE])
    trans_df[WEEKDAY] = pd.to_datetime(trans_df[DATE]).apply(lambda x: x.weekday())
    trans_df[WORK_WEEK] = pd.to_datetime(trans_df[DATE]).apply(lambda x: x.isocalendar()[1])
    trans_df[MONTH] = pd.to_datetime(trans_df[DATE]).apply(lambda x: x.month)
    trans_df[DAY] = pd.to_datetime(trans_df[DATE]).apply(lambda x: x.day)
    # Add Income column
    trans_df[INCOME] = trans_df[AMOUNT] < 0
    # Calculate total & num of incomes for week & month
    last_week_incomes = get_last_n_days_incomes(trans_df.iloc[0], 7)
    last_month_incomes = get_last_n_days_incomes(trans_df.iloc[0], 30)
    trans_df[TOTAL_INCOMES_LAST_WEEK] = round(-last_week_incomes[AMOUNT].sum(), 2) if not last_week_incomes.empty else 0
    trans_df[NUM_OF_INCOMES_LAST_WEEK] = len(last_week_incomes.index)
    trans_df[TOTAL_INCOMES_LAST_MONTH] = round(-last_month_incomes[AMOUNT].sum(), 2) if not last_month_incomes.empty else 0
    trans_df[NUM_OF_INCOMES_LAST_MONTH] = len(last_month_incomes.index)
    return trans_df


# endregion

if __name__ == '__main__':
    read_users_and_transactions_files("./users.json", "./transactions_clean.json")
    all_data = part_a()
    all_data.to_csv('data.csv', index=False)

    # debug
    all_data = pd.read_csv('data.csv')
    global all_categories
    all_categories = [u'Bicycles', u'Shops', u'Food and Drink', u'Restaurants', u'Car Service', u'Ride Share', u'Travel',
                      u'Airlines and Aviation Services', u'Coffee Shop', u'Gyms and Fitness Centers', u'Recreation', u'Deposit', u'Transfer',
                      u'Credit Card', u'Payment', u'Credit', u'Discount Stores', u'Service', u'Telecommunication Services', u'Music, Video and DVD',
                      u'Financial', u'Computers and Electronics', u'Video Games', u'Warehouses and Wholesale Stores', u'Debit', u'Digital Purchase',
                      u'Supermarkets and Groceries', u'Cable', u'Gas Stations', u'Department Stores', u'Bank Fees', u'Overdraft', u'Interest',
                      u'Interest Charged', u'Wire Transfer', 'subscription_cat', u'Personal Care', u'ATM', u'Withdrawal', u'Pharmacies']
    # end debug

    part_b(all_data)
    part_c()
