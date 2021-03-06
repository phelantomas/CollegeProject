import datetime
import os.path
import sys
import time
import json

import pandas as pd
from PyQt4.QtCore import *
from PyQt4 import QtCore
from PyQt4.QtGui import *
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

import collect_prices
import collect_tweets
import predict
import process_tweets
import notify
import crypto_config

NOTIFY_CONFIG = json.load(open("notify_config.json"))
formatted_cryptocurrency_tweets = []
num_of_passes = 0
logo_path = "/home/phelan/Project/CollegeProject/crypto_logo.png"
NUMBER_OF_MINUTES = 3

class SentimentTraderWindow(QTabWidget):
    def __init__(self, parent=None):
        super(SentimentTraderWindow, self).__init__(parent)

        #Create threads and connections
        self.workerThread = WorkerThread()
        self.connect(self.workerThread, QtCore.SIGNAL("update_tweets_table"), self.update_tweets_table)
        self.connect(self.workerThread, QtCore.SIGNAL("analyse_data"), self.analyse_data)
        self.connect(self.workerThread, QtCore.SIGNAL("update_current_sentiment"), self.update_current_sentiment)

        self.home = QWidget()
        self.cryptocurrency_home = QScrollArea()
        self.cryptocurrency_home.setWidgetResizable(True)
        self.notification_home = QWidget()

        self.addTab(self.home, "Home")
        self.addTab(self.cryptocurrency_home, crypto_config.CRYPTOCURRENCY)
        self.addTab(self.notification_home, "Notification")

        self.cryptocurrency_sentiment_label = QLabel()

        self.cryptocurrency_table = QTableWidget()

        #####
        self.list_actual_change = []
        self.list_predicted_change = []
        ####

        #plotting cryptocurrency
        self.cryptocurrency_xlist = []
        self.cryptocurrency_y_actual_list = []
        self.cryptocurrency_linear_y_predict_list = []
        self.cryptocurrency_forest_y_predict_list = []
        self.cryptocurrency_average_y_predict_list = []
        self.cryptocurrency_current_price = []
        self.cryptocurrency_plot_time = []
        formatted_cryptocurrency_tweets = []

        #Tables for tweets
        header = ['TimeStamp', 'Tweet', 'Sentiment']

        self.cryptocurrency_table.setColumnCount(3)
        self.cryptocurrency_table.setColumnWidth(0, 170)
        self.cryptocurrency_table.setColumnWidth(1, 800)

        self.cryptocurrency_table.setHorizontalHeaderLabels(header)
        self.cryptocurrency_table.horizontalHeader().setResizeMode(1, QHeaderView.Stretch)

        self.cryptocurrencyFigure = Figure()

        # this is the Canvas Widget that displays the `figure`
        # it takes the `figure` instance as a parameter to __init__
        self.cryptocurrencyCanvas = FigureCanvas(self.cryptocurrencyFigure)

        self.cryptocurrency_ax = self.cryptocurrencyFigure.add_subplot(111)

        self.home_UI()
        self.cryptocurrency_home_UI()
        self.notification_home_UI()
        self.setWindowTitle("Sentment Trader")
        self.setWindowIcon(QIcon(logo_path))
        self.resize(1450, 720)

        self.process_data()

    def home_UI(self):
        layout = QFormLayout()
        label_image = QLabel()
        label_image.setAlignment(Qt.AlignCenter)
        logo = QPixmap(logo_path)
        label_image.setPixmap(logo)
        layout.addWidget(label_image)

        disclaimer_text = "**DISCLAIMER! This application does not promise to be 100% accurate, we are not " \
                          "responsible for any losses that might occur trading " + crypto_config.CRYPTOCURRENCY + "."
        disclaimer_label = QLabel(disclaimer_text)

        instructions_text = "Application may take a few hours before building up adequet training set of an unseen cryptocurrency"
        instructions_label = QLabel(instructions_text)
        disclaimer_label.setAlignment(Qt.AlignCenter)
        instructions_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(disclaimer_label)
        layout.addWidget(instructions_label)
        self.setTabText(0, "Home")
        self.home.setLayout(layout)

    def cryptocurrency_home_UI(self):
        layout = QFormLayout()
        layout.addWidget(self.cryptocurrency_sentiment_label)
        # this is the Navigation widget
        # it takes the Canvas widget and a parent
        self.cryptocurrency_toolbar = NavigationToolbar(self.cryptocurrencyCanvas, self)

        layout.addWidget(self.cryptocurrency_toolbar)
        layout.addWidget(self.cryptocurrencyCanvas)
        layout.addWidget(self.cryptocurrency_table)

        self.setTabText(1, crypto_config.CRYPTOCURRENCY)
        self.cryptocurrency_home.setLayout(layout)

    def notification_home_UI(self):
        layout = QFormLayout()
        self.setTabText(2, "Notification")

        self.email_checkbox = QCheckBox("Email Notifications")
        self.push_checkbox = QCheckBox("Push Notifications")
        layout.addRow(self.email_checkbox)
        layout.addRow(self.push_checkbox)

        max_label = QLabel("Alert Above")
        layout.addRow(max_label)
        self.max_value = QDoubleSpinBox()
        self.max_value.setMaximum(1000)
        self.max_value.setMinimum(-1000)
        layout.addRow(self.max_value)
        self.min_value = QDoubleSpinBox()
        self.min_value.setMaximum(1000)
        self.min_value.setMinimum(-1000)
        min_label = QLabel("Alert Below")
        layout.addRow(min_label)
        layout.addRow(self.min_value)

        self.email_address = QLineEdit()
        layout.addRow("Email", self.email_address)

        self.button = QPushButton('Submit', self)
        self.button.clicked.connect(self.handleButton)
        layout.addWidget(self.button)
        self.notification_home.setLayout(layout)

    def handleButton(self):
        global NOTIFY_CONFIG
        NOTIFY_CONFIG = {"NOTIFY_CRYPTOCURRENCY_EMAIL": self.email_checkbox.isChecked(),
                                "NOTIFY_CRYPTOCURRENCY_PUSH": self.push_checkbox.isChecked(),
                                "CRYPTOCURRENCY_PRICE_ABOVE": float(self.max_value.value()),
                                "CRYPTOCURRENCY_PRICE_BELOW": float(self.min_value.value()),
                                "EMAIL": str(self.email_address.text())}

        with open("notify_config.json", "w") as j_file:
            json.dump(NOTIFY_CONFIG, j_file)

        print("Is email checked" + str(self.email_checkbox.isChecked()))
        print("Is push checked" + str(self.push_checkbox.isChecked()))
        print("Max Value " + str(self.max_value.value()))
        print("Min Value " + str(self.min_value.value()))
        print("Email is " + str(self.email_address.text()))

        self.email_checkbox.setChecked(False)
        self.push_checkbox.setChecked(False)
        self.max_value.clear()
        self.min_value.clear()
        self.email_address.clear()

    def plot(self, linear_predict_change, forest_predict_change):
        ''' plot change'''
        if len(self.cryptocurrency_linear_y_predict_list) is 0:#Init
            self.cryptocurrency_linear_y_predict_list.append(self.cryptocurrency_current_price[-1])
            self.cryptocurrency_forest_y_predict_list.append(self.cryptocurrency_current_price[-1])
            self.cryptocurrency_average_y_predict_list.append(self.cryptocurrency_current_price[-1])

        print("Current " + str(self.cryptocurrency_current_price[-1]))
        self.cryptocurrency_linear_y_predict_list.append(float(self.cryptocurrency_current_price[-1]) + float(linear_predict_change))
        self.cryptocurrency_forest_y_predict_list.append(float(self.cryptocurrency_current_price[-1]) + float(forest_predict_change))
        self.cryptocurrency_average_y_predict_list.append((self.cryptocurrency_linear_y_predict_list[-1] +
                                                          self.cryptocurrency_forest_y_predict_list[-1])/2)

        if len(self.cryptocurrency_current_price) > 8:
            current_price_graph = self.cryptocurrency_current_price[-8:]
            linear_y_predict_list_graph = self.cryptocurrency_linear_y_predict_list[-9:]
            forest_y_predict_list_graph = self.cryptocurrency_forest_y_predict_list[-9:]
            average_y_predict_list_graph = self.cryptocurrency_average_y_predict_list[-9:]
            predict_xList = self.cryptocurrency_plot_time[-8:]
        else:
            current_price_graph = self.cryptocurrency_current_price
            linear_y_predict_list_graph = self.cryptocurrency_linear_y_predict_list
            forest_y_predict_list_graph = self.cryptocurrency_forest_y_predict_list
            average_y_predict_list_graph = self.cryptocurrency_average_y_predict_list
            predict_xList = self.cryptocurrency_plot_time[:]
        predict_xList.append("Predicted Change")

        linear_y_predict_list_graph = [round(float(i)) for i in linear_y_predict_list_graph]
        forest_y_predict_list_graph = [round(float(i)) for i in forest_y_predict_list_graph]
        average_y_predict_list_graph = [round(float(i)) for i in average_y_predict_list_graph]
        current_price_graph = [round(float(i)) for i in current_price_graph]

        ax = self.cryptocurrencyFigure.add_subplot(111)
        ax.clear()
        ax.cla()
        ax.remove()
        ax = self.cryptocurrencyFigure.add_subplot(111)
        ax.set_title(crypto_config.CRYPTOCURRENCY + ' Price Previous Hours')
        ax.set_ylabel('Price ($)')
        ax.set_xlabel('Time (h)')
        ax.grid()
        #Scales chart dynamically
        ax.set_ylim((min(min(linear_y_predict_list_graph),min(forest_y_predict_list_graph), min(current_price_graph)) - 5),
                    (max(max(linear_y_predict_list_graph), max(forest_y_predict_list_graph), max(current_price_graph)) + 5))

        print(current_price_graph)
        print(predict_xList)
        print(linear_y_predict_list_graph)
        print(forest_y_predict_list_graph)

        ax.plot(predict_xList[:-1], current_price_graph, label='Actual Price')
        ax.plot(predict_xList, linear_y_predict_list_graph, label='Linear Prediction')
        ax.plot(predict_xList, forest_y_predict_list_graph, label='Forest Prediction')
        ax.plot(predict_xList, average_y_predict_list_graph, label='Average Prediction')
        ax.legend(loc='upper left')
        self.cryptocurrencyCanvas.draw_idle()

    def process_data(self):
        self.workerThread.start()

    def update_tweets_table(self, tweets, refresh):
        print(len(tweets))
        # do at end
        if refresh:
            print(refresh)
            for i in reversed(range(self.cryptocurrency_table.rowCount())):
                self.cryptocurrency_table.removeRow(i)
            #self.cryptocurrency_table.rowCount(0)
        for tweet in tweets:
            rowPosition = self.cryptocurrency_table.rowCount()
            self.cryptocurrency_table.insertRow(rowPosition)
            self.cryptocurrency_table.setItem(rowPosition, 0, QTableWidgetItem(str(tweet['created_at'])))
            self.cryptocurrency_table.setItem(rowPosition, 1, QTableWidgetItem(
                str(tweet['formatted_text'].encode('utf8'))))  # tweet['formatted_text']
            self.cryptocurrency_table.setItem(rowPosition, 2, QTableWidgetItem(str(tweet['sentiment']['compound'])))


    def get_current_price(self, exchange):
        timeout = 1
        str_error = "No Price Yet"
        while str_error:
            try:
                price_info = collect_prices.get_price_info(exchange)
                j_info = json.loads(price_info)
                str_error = None
            except Exception as str_error:
                print(str_error)
                time.sleep(timeout)
        return j_info

    def update_current_sentiment(self, average_compound):
        self.cryptocurrency_sentiment_label.setText("Current Sentiment : " + str(average_compound))

    def notify_user(self, predicted_change, cryptocurrency):
        if NOTIFY_CONFIG["NOTIFY_CRYPTOCURRENCY_PUSH"] is True:
            if (float(predicted_change) >= NOTIFY_CONFIG['CRYPTOCURRENCY_PRICE_ABOVE'] or float(predicted_change)
                    <= NOTIFY_CONFIG['CRYPTOCURRENCY_PRICE_BELOW']):
                notify.push_notification(predicted_change, cryptocurrency)
        if NOTIFY_CONFIG["NOTIFY_CRYPTOCURRENCY_EMAIL"] is True:
            if (float(predicted_change) >= NOTIFY_CONFIG['CRYPTOCURRENCY_PRICE_ABOVE'] or float(predicted_change)
                    <= NOTIFY_CONFIG['CRYPTOCURRENCY_PRICE_BELOW']):
                notify.send_email(predicted_change, cryptocurrency, NOTIFY_CONFIG["EMAIL"])


    def analyse_data(self, filename, exchange, coin):
        global formatted_cryptocurrency_tweets
        global predict_change
        tweetsInHour = []

        tweets_from_one_hour = datetime.datetime.now() - datetime.timedelta(hours=2)#2 hours now due to time saving

        for tweet in formatted_cryptocurrency_tweets:
            created_at = datetime.datetime.strptime(tweet['created_at'], '%Y-%m-%dT%H:%M:%S')
            if created_at > tweets_from_one_hour:
                tweetsInHour.append(tweet)
        formatted_cryptocurrency_tweets = []

        print("Number of unique tweets in an hour for " + coin + " is " + str(len(tweetsInHour)))

        file_exists = os.path.isfile(filename)

        j_info = self.get_current_price(exchange)

        change = j_info['ticker']['change']
        volume = j_info['ticker']['volume']
        price = j_info['ticker']['price']
        timestamp = j_info['timestamp']

        # average compound
        average_compound = float(sum(d['sentiment']['compound'] for d in tweetsInHour)) / len(
            tweetsInHour)

        cryptoFeature = {'TimeStamp': [timestamp], 'Sentiment': [average_compound], 'Volume': [volume],
                         'Change': [change], 'Price': [price], 'NoOfTweets': [len(tweetsInHour)]}

        pd.DataFrame.from_dict(data=cryptoFeature, orient='columns').to_csv(filename, mode='a',
                                                                            header=not file_exists)
        # Make Predictions
        linear_predict_change = predict.generate_linear_prediction_model(cryptoFeature, filename)
        forest_predict_change = predict.generate_forest_prediction_model(cryptoFeature, filename)

        self.notify_user(linear_predict_change, coin)
        #self.notify_user(forest_predict_change, coin)

        #Plotting
        self.cryptocurrency_current_price.append(price)
        self.cryptocurrency_plot_time.append(datetime.datetime.now().strftime("%H:%M:%S"))
        print(linear_predict_change)
        print(forest_predict_change)

        self.plot(linear_predict_change, forest_predict_change)

        if (linear_predict_change):
            print("The sentiment of the last 60 minutes for " + coin + " is : " + str(
                cryptoFeature['Sentiment'][0]) + " - The predicted change in price is : " + linear_predict_change)


class WorkerThread(QThread):
    def __init__(self, parent=None):
        super(WorkerThread, self).__init__(parent)

    def run(self):
        global formatted_cryptocurrency_tweets
        global num_of_passes

        num_of_passes += 1

        print('Pass number : ' + str(num_of_passes))

        # cryptocurrency
        cryptocurrencyTweets = collect_tweets.collect_tweets(crypto_config.CRYPTOCURRENCY)
        cryptocurrencyTweets = process_tweets.process_tweets_from_main(cryptocurrencyTweets)

        tweets_for_table = [x for x in cryptocurrencyTweets if x not in formatted_cryptocurrency_tweets]
        formatted_cryptocurrency_tweets.extend(cryptocurrencyTweets)

        # remove duplicated tweets
        formatted_cryptocurrency_tweets = [i for n, i in enumerate(formatted_cryptocurrency_tweets)
                                                if i not in formatted_cryptocurrency_tweets[n + 1:]]

        refresh = False
        if num_of_passes is NUMBER_OF_MINUTES:
            refresh = True
        self.emit(SIGNAL("update_tweets_table"), tweets_for_table, refresh)

        # average compound
        average_compound = float(sum(d['sentiment']['compound'] for d in formatted_cryptocurrency_tweets)) / len(
            formatted_cryptocurrency_tweets)
        self.emit(SIGNAL("update_current_sentiment"), average_compound)

        if num_of_passes is NUMBER_OF_MINUTES:
            num_of_passes = 0
            self.emit(SIGNAL("analyse_data"), crypto_config.FEATURE_FILE,
                      crypto_config.EXCHANGE, crypto_config.CRYPTOCURRENCY)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SentimentTraderWindow()
    timer = QTimer()
    timer.timeout.connect(window.process_data)
    timer.start(60000)
    window.show()
    sys.exit(app.exec_())
