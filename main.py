#!/usr/bin/python3
# a UI for timeline viewing, filtering and searching
# 2020 Jeff Bryner
#
# A note on the functions; semi-following an old-school pattern of:
# ui=user interface function (change look/feel only)
# ti=transaction interface function (stitch the ui/ei/di layers together into a transaction)
# ei=external interface (talk to something outside of us, filesystem, socket, etc)
# di=data interface (sort, filter, transform data)
#
# Helps to avoid the old Visual Basic style code mess of same code pasted behind many buttons.
#

import os
import sys
import string
from optparse import OptionParser
from io import StringIO
from kivy.app import App
from kivy.animation import Animation
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.adapters.listadapter import ListAdapter
from kivy.uix.listview import ListView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.uix.widget import Widget
from threading import Thread
from kivy.properties import StringProperty, BooleanProperty, NumericProperty, ObjectProperty
from kivy.config import Config
from kivy.uix.popup import Popup
from kivy.logger import Logger
import pandas
from random import randint
from time import sleep
from collections import Counter
from functools import partial
from datetime import datetime
from collections import OrderedDict

class TimeEntry(Widget):
    pass


class YearWidget(RelativeLayout):
    display=StringProperty('')
    items=NumericProperty(0)
    maxitems=NumericProperty(1)
    year=NumericProperty(0)
    selected=BooleanProperty(False)

    def tiFilterYear(self):
        #unselect everybody else but us
        print(self)
        print(self.display)
        print(self.selected)
        # for c in self.children:
        #     print(c)
        # for c in self.children:
        #     if c.selected:
        #         print(c)
        #    c.selected=False
        #self.selected=True
        #tell the master to filter its results
        # self.parent.parent.parent.parent.parent.parent.tiFilterYear(self.year)
        #self.parent.parent.parent.parent.parent.tiFilterYear(self.year)

class Wait(BoxLayout):
    pass

class LoadDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)

class macFileRead(Thread):
    df = None
    parent=None
    filename=None

    def run(self):
        self.parent.dfready=False

        #sample the file headers to see what we are dealing with:
        headers=open(self.filename).readlines()[:1][0].strip().lower()

        if 'date' in headers and 'meta' in headers:
            #classic mactime file
            #'date,size,type,mode,uid,gid,meta,file name'
            self.df=pandas.read_csv(self.filename,parse_dates=True,keep_date_col=True,low_memory=False)
            self.df['Date']=pandas.to_datetime(self.df['Date'])
            self.df.set_index('Date', inplace=True, drop=False)
            self.df.sort_index(inplace=True)

        if 'time' in headers and 'macb' in headers:
            #log2timeline file
            #'date,time,timezone,macb,source,sourcetype,type,user,host,short,desc,version,filename,inode,notes,format,extra'
            # read in the date,time fields as one field to index as datetime index.
            self.df=pandas.read_csv(self.filename,keep_date_col=True,index_col=None,parse_dates=[[0,1]],low_memory=False,error_bad_lines=False)

            #fixup field names:
            headers=headers.replace('date','l2tdate')
            headers=headers.title()
            headerColumns=headers.split(',')
            headerColumns.insert(0,'Date')
            #rename the columns in the dataframe
            self.df.columns=headerColumns

            #remove columns with dup date to avoid pandas issues
            del self.df['L2Tdate']
            del self.df['Time']

            #index the dataframe
            self.df['Date']=pandas.to_datetime(self.df['Date'])
            self.df.set_index('Date', inplace=True, drop=False)
            self.df.sort_index(inplace=True)
            # self.df.index=self.df['Date']
            # self.df.index.name='Date'
            # self.df.reindex()
            # self.df = self.df.sort_index()

        self.parent.df = self.df
        self.parent.dfsel=self.df
        self.parent.dfready=True
        self.parent.status=f'{len(self.df)} items ready'

class pytimeline(RelativeLayout):
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     self.status=StringProperty('')
    #     self.loadfile = ObjectProperty(None)
    #     self.df=pandas.DataFrame()
    #     self.dfready=BooleanProperty(False)
    #     self.dfsel=pandas.DataFrame()
    #     self.timeitems=BoxLayout()
    #     self.SearchText=ObjectProperty(TextInput)
    #     self.printFormat=OrderedDict()

    status=StringProperty('')
    loadfile = ObjectProperty(None)
    df=pandas.DataFrame()
    dfready=BooleanProperty(False)
    dfsel=pandas.DataFrame()
    timeitems=BoxLayout()
    SearchText=ObjectProperty(TextInput)
    printFormat=OrderedDict()

    def tiFilterText(self,searchText):
        #filter the dataframe by case-insensitive fields matching the text
        #search keywords:
        #fieldname: value    <--makes us search only that fieldname for the value
        #! fieldname: value  <--search for anything not matching the value in the field
        #value               <--search only the file name (mactime)  or 'desc' field (log2timeline)

        sText=""
        dfFilter=None
        Logger.debug(f'df.sel.columns {self.dfsel.columns}')
        if ':' in searchText:
            #likely we are searching a specific field:
            for field in list(self.printFormat.keys()):
                scommand='%s: '%field.lower()
                if (scommand) in searchText:
                    sText=searchText.replace(searchText.lower(),scommand,'').strip()
                    if '!' in searchText:
                        sText=sText.replace('!','').strip()
                        dfFilter=self.dfsel[field].map(lambda x:sText not in str(x.decode('ascii',errors='ignore')).lower() )
                    else:
                        dfFilter=self.dfsel[field].map(lambda x:sText in str(x.decode('ascii',errors='ignore')).lower() )

        #if it's not set yet, it's not a column match, try file/description.
        if dfFilter is None and 'File Name' in self.dfsel.columns:
            if '!' in searchText:
                sText=sText.replace('!','').strip()
                #dfFilter=self.dfsel['File Name'].map(lambda x:sText.lower() not in str(x.decode('ascii',errors='ignore')).lower() )
                dfFilter=self.dfsel['File Name'].str().lower()
            else:
                dfFilter=self.dfsel['File Name'].map(lambda x:searchText.lower() in x.lower() )
        elif dfFilter is None and 'Desc' in self.dfsel.columns:
            if '!' in searchText:
                sText=sText.replace('!','').strip()
                dfFilter=self.dfsel['Desc'].map(lambda x:sText.lower() not in str(x.decode('ascii',errors='ignore')).lower() )
            else:
                dfFilter=self.dfsel['Desc'].map(lambda x:searchText.lower() in str(x.decode('ascii',errors='ignore')).lower() )

        Logger.info(f'SearchText: {searchText}')
        #Logger.info(f'dfFilter: {dfFilter}')

        if dfFilter is None or len(self.dfsel[dfFilter])==0:
            self.status='No matches'
        else:
            #we've got something, so show it and filter results.
            sel=self.dfsel[dfFilter]
            self.tiShowDataFrame(sel)
            #save our filter
            self.dfsel=sel

    def tiFilterDate(self,beginDate,endDate):
        #in case the user didn't enter a full date
        #set the defaults to whatever is in our view: beginning, ending
        #helps them whittle it down without having to type full date/time ranges.

        #beginning default date is the first thing in our list, first day, first second
        bdateDefault=datetime(self.dfsel.index.year[0],self.dfsel.index.month[0],1,0,0,0)

        #ending default date is the first day of the last thing in our list, end of day
        pos=len(self.dfsel.index)-1
        edateDefault=datetime(self.dfsel.index.year[pos],self.dfsel.index.month[pos],1, 23, 59,59)

        eDate=None
        bDate=None
        sel=''
        try:
            if len(beginDate.strip())>0:
                #bDate=pandas.lib.tslib.parse_date(beginDate.strip(),default=bdateDefault)
                bDate=pandas.to_datetime(beginDate.strip())
            if len(endDate.strip())>0:
                #eDate=pandas.lib.tslib.parse_date(endDate.strip(),default=edateDefault)
                eDate=pandas.to_datetime(endDate.strip())
        except Exception as e:
            self.status='invalid date range' + str(e)
            return

        Logger.debug(f'Searching from {bDate} to {eDate}')

        if not bDate ==None and not eDate ==None:
            #sanity
            try:
                if bDate< eDate:
                    sel=self.dfsel[self.dfsel.index>= bDate]
                    sel=sel[sel.index<= eDate]
                else:
                    self.status='invalid date range'
                    return
            except Exception as e:
                self.status=str(e)
                return
        elif not bDate ==None:
            sel=self.dfsel[self.dfsel.index>= bDate]
        elif not eDate == None:
            sel=self.dfsel[self.dfsel.index<= eDate]
        if len(sel)==0:
            self.status='No matches'
        else:
            #we've got something, so show it and filter results.
            self.tiShowDataFrame(sel)
            #save our filter
            self.dfsel=sel

    def tiFilterYear(self,*year):
        Logger.info(f'filtering for year {year}')
        self.timeitems.clear_widgets()
        content = Wait()
        self.timeitems.add_widget(content)
        #get the subset of the data frame that matches the year:
        #first X matches?
        #sel=self.df[self.df.index.year==year][0:100]
        self.dfsel=self.df[self.df.index.year==year].copy()
        Logger.info(f'dfsel length {len(self.dfsel)}')
        self.tiShowDataFrame(self.dfsel)

    def tiShowDataFrame(self,dataframe):
        #clear the old
        self.timeitems.clear_widgets()
        self.columnHeadings.clear_widgets()

        #add the index back as a column so we can see it
        #dataframe['Date']=dataframe.index
        #dataframe['Date']=pandas.to_datetime(dataframe['Date'])
        #dataframe.set_index('Date', inplace=True, drop=False)
        #convert to a list of dictionaries to get all the values, full strings, etc.
        ilist=list()
        for v in dataframe.values:
            adict=dict()
            for c in range(len(dataframe.columns)):
                adict[dataframe.columns[c]]=str(v[c])
            ilist.append(adict)


        #create the format string
        sFormatString=""
        #print only what we want:
        for pf in list(self.printFormat.keys()):
            if pf in list(ilist[0].keys()):
                sFormatString += self.printFormat[pf] + ' '

        items=list()
        for i in ilist:
            items.append(sFormatString.format(**i))
            #items.append("{Date} {Size:>10} {Type} {Mode} {UID:4} {GID:4} {Meta:15} {File Name}".format(**i))

        #add the items to the listview

        list_adapter=ListAdapter(data=items,template='TimeEntry')
        list_view = ListView(adapter=list_adapter)
        self.timeitems.add_widget(list_view)

        #add the header
        headeritems=list()
        #headeritems.append("{0:19} {1:>10} {2} {3:12} {4:4} {5:4} {6:15} {7}".format('Date','Size','Type','Mode','UID','GID','Meta','File Name'))
        #make a dict for the header to be formatted the same as the data:
        columnDict=dict.fromkeys(dataframe.columns.tolist())
        for c in list(columnDict.keys()):
            columnDict[c]=c
        headeritems.append(sFormatString.format(**columnDict))

        header_list_adapter=ListAdapter(data=headeritems,template='TimeEntry')
        header_list_view = ListView(adapter=header_list_adapter)
        self.columnHeadings.add_widget(header_list_view)

        self.status='%d items'%len(dataframe.values)

    def uiDismissLoad(self):
        self.load.dismiss()

    def uiShowLoad(self):
        content = LoadDialog(load=self.tiStartLoadFile, cancel=self.uiDismissLoad)
        self.load = Popup(title="Load CSV timeline file", content=content, size_hint=(0.5, 0.5))
        self.load.open()

    def uiClearScreen(self,timegraph=False):
        self.timeitems.clear_widgets()
        self.columnHeadings.clear_widgets()
        if timegraph:
            self.timegraph.clear_widgets()
        self.dfsel=self.df.copy()

    def uiShowWait(self,dt):
        self.status="..."
        content = Wait()
        self.uiClearScreen()
        self.timeitems.add_widget(content)

    def tiStartLoadFile(self,path,filename):
        #use the kivy scheduler to show a wait ui, start the read thread and schedule the load transaction
        Clock.schedule_once(partial(self.uiShowWait))

        self.load.dismiss()
        self.readThread=macFileRead()
        self.readThread.filename=os.path.join(path,filename[0])
        self.readThread.parent=self
        self.readThread.start()
        Clock.schedule_once(partial(self.tiFinishLoadFile),1)

    def tiFinishLoadFile(self,dt):

        #self.df=read_csv(os.path.join(path, filename[0]),parse_dates=True,keep_date_col=True,index_col=0)
        if not self.dfready:
            #thread isn't finished loading yet.
            Clock.schedule_once(partial(self.tiFinishLoadFile),1)
            return

        #We format the string output by creating a dict of fields we care about
        #in the order we want them
        #with a python format string for how we want to see them.
        #Field names are a combination of what's in mactime and log2timeline, it's only the order that matters.
        #if the field doesn't exist we don't print it, if it's not in this dict we don't print it.
        self.printFormat=OrderedDict()
        self.printFormat['Date']='{Date:<19}'
        self.printFormat['Size']='{Size:>10}'
        self.printFormat['Macb']='{Macb:^4}'
        self.printFormat['Type']='{Type:15}'
        self.printFormat['Mode']='{Mode:12}'
        self.printFormat['UID']='{UID:4}'
        self.printFormat['GID']='{GID:4}'
        self.printFormat['User']='{User:4}'
        self.printFormat['Inode']='{Inode:^5}'
        self.printFormat['Meta']='{Meta:15}'
        self.printFormat['Source']='{Source:^6}'
        self.printFormat['Format']='{Format:^17}'
        #self.printFormat['Host']='{Host}'
        self.printFormat['Desc']='{Desc:<}'
        self.printFormat['File Name']='{File Name:<}'

        #clear the old
        self.uiClearScreen()

        #create the year scrollview UI and timegrid
        sview=ScrollView()
        self.timegraph.add_widget(sview)

        #some time math to help size the UI
        years=self.df.index.year
        uniqueYears=Counter(years)
        yearCount=len(uniqueYears)

        timegrid=GridLayout(rows=1,cols=yearCount,spacing=5,padding=0,size_hint_x=1.2)

        #use the dataframe index to itemize the years for the lower display
        #calc max year size to scale the bars
        maxitems=1
        for x in uniqueYears:
            maxitems=max(maxitems,uniqueYears[x])

        for x in uniqueYears:
            yearItems=uniqueYears[x]
            ayearWidget=YearWidget(items=yearItems,display=str(x),year=int(x),maxitems=maxitems)
            timegrid.add_widget(ayearWidget)

        sview.add_widget(timegrid)
        self.status="ready"



class pytimelineApp(App):
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)

    def build_config(self, config):
        Config.set('kivy','log_enable','0')
        print((options,Config))
        if options.debug:
            print('debug!')
            Config.set('kivy','log_level','debug')
        else:
            Config.set('kivy','log_level','critical')

        Config.set('graphics','width',1500)
        Config.set('graphics','height',1024)

    def build(self):
        kvLayout=pytimeline()
        #a lil silly, but we load the wait and clear it so kivy loads the 'loading.gif', else it lags later and seems unresponsive.
        kvLayout.uiShowWait(dt=None)
        kvLayout.uiClearScreen()
        kvLayout.uiShowLoad()
        return kvLayout


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-d", "--debug",action="store_true", dest="debug", default=True, help="turn on debugging output")
    (options,args) = parser.parse_args()
    pytimelineApp().run()