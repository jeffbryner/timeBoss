#!/usr/bin/python2
import os
import sys
import string
from optparse import OptionParser
from StringIO import StringIO
from kivy.app import App
from kivy.animation import Animation
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.adapters.dictadapter import DictAdapter
from kivy.adapters.simplelistadapter import SimpleListAdapter
from kivy.adapters.listadapter import ListAdapter
from kivy.uix.listview import ListView
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.uix.widget import Widget
from threading import Thread
from kivy.properties import StringProperty, BooleanProperty, NumericProperty, ObjectProperty
from kivy.config import Config
from kivy.uix.popup import Popup
import pandas
from random import randint
from time import sleep
from collections import Counter
from functools import partial


class TimeEntry(Widget):
    pass
    

class YearWidget(RelativeLayout):
    display=StringProperty('')
    items=NumericProperty(0)
    maxitems=NumericProperty(1)
    year=NumericProperty(0)
    selected=BooleanProperty(False)

    
    def filterYear(self):
        #unselect everybody else but us, precious
        for c in self.parent.children:
            c.selected=False
        self.selected=True
        #tell the master to filter its resultses.
        self.parent.parent.parent.parent.parent.parent.filterYear(self.year)

class Wait(BoxLayout):
    pass
class LoadDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)   

class macFileRead(Thread):
    #set as a thread to allow for large file load times into pandas
    def __init__(self, *largs, **kwargs):
        super(macFileRead, self).__init__(*largs, **kwargs)
        self.df = None
        self.parent=None
        self.filename=None
        
    def run(self):        
        self.df=pandas.read_csv(self.filename,parse_dates=True,keep_date_col=True,index_col=0)
        self.parent.df = self.df



    
class pytimeline(RelativeLayout):
    status=StringProperty('')
    loadfile = ObjectProperty(None)
    df=pandas.DataFrame()
    dftime=pandas.DataFrame()
    timeitems=ObjectProperty()
    SearchText=ObjectProperty(TextInput)
    
    def filterText(self,searchText):        
        dfFilter=self.dftime['File Name'].map(lambda x:string.lower(searchText) in string.lower(x) )
        if len(self.dftime[dfFilter])==0:
            self.status='No matches'        
        else:
            sel=self.dftime[dfFilter]
            self.showDataFrame(sel)
        
    def filterYear(self,year):        

        #get the subset of the data frame that matches the year: 
        #first X matches?
        #sel=self.df[self.df.index.year==year][0:100]
        sel=self.df[self.df.index.year==year]
        self.dftime=sel
        self.showDataFrame(sel)


    def showDataFrame(self,dataframe):
        #clear the old
        self.timeitems.clear_widgets()
        self.columnHeadings.clear_widgets()
        
        #add the index back as a column so we can see it
        dataframe['Date']=dataframe.index
        
        #convert to a list of dictionaries to get all the values, full strings, etc.
        ilist=list()
        for v in dataframe.values: 
            adict=dict()
            for c in range(len(dataframe.columns)):
                adict[dataframe.columns[c]]=str(v[c])
            ilist.append(adict)
        
        #format the string output
        items=list()
        for i in ilist:
            items.append("{Date} {Size:>10} {Type} {Mode} {UID:4} {GID:4} {Meta:15} {File Name}".format(**i))
        
        #add the items to the listview
        
        list_adapter=ListAdapter(data=items,template='TimeEntry')
        list_view = ListView(adapter=list_adapter)
        self.timeitems.add_widget(list_view)
        
        #add the header
        headeritems=list()
        headeritems.append("{0:19} {1:>10} {2} {3:12} {4:4} {5:4} {6:15} {7}".format('Date','Size','Type','Mode','UID','GID','Meta','File Name'))
        header_list_adapter=ListAdapter(data=headeritems,template='TimeEntry')
        header_list_view = ListView(adapter=header_list_adapter)
        self.columnHeadings.add_widget(header_list_view)
        
        self.status='%d items'%len(dataframe.values)        
        
    def dismiss_popup(self):
        self._popup.dismiss()

    def show_load(self):
        content = LoadDialog(load=self.hide_load, cancel=self.dismiss_popup)        
        self._popup = Popup(title="Load CSV timeline file", content=content, size_hint=(0.5, 0.5))
        self._popup.open()

    def show_wait(self,dt):
        self.status="please wait..."
        content = Wait()
        self._wait=Popup(title="     .:|Loading|:.",content=content,size_hint=(.1,.1))
        self._wait.open()

    def hide_wait(self,dt):
        self._wait.dismiss()
        self.status='ready'                

    def hide_load(self,path,filename):
        Clock.schedule_once(partial(self.show_wait))
        Clock.schedule_once(partial(self.dfload),1)
        self._popup.dismiss()
        self.readThread=macFileRead()
        self.readThread.filename=os.path.join(path,filename[0])
        self.readThread.parent=self
        self.readThread.start()        
        
    
    def dfload(self,dt):

        #self.df=read_csv(os.path.join(path, filename[0]),parse_dates=True,keep_date_col=True,index_col=0)
        if len(self.df) == 0:
            #thread isn't finished loading yet.
            Clock.schedule_once(partial(self.dfload),1)
            return
        
        Clock.schedule_once(partial(self.hide_wait))
        
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

        

class pytimelineApp(App):           
    def build_config(self, config):
        Config.set('graphics','width',1650)
        Config.set('graphics','height',1024)
        Config.set('kivy','log_level','info')
        Config.set('kivy','log_enable','0')        
        
        
    def build(self):
        kvLayout=pytimeline()
        kvLayout.show_load()
        return kvLayout


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-i", dest='input', default="stdin",help="input: stdin default, csv filename of timeline data")
    parser.add_option("-d", "--debug",action="store_true", dest="debug", default=False, help="turn on debugging output")    

    (options,args) = parser.parse_args()
    
    pytimelineApp().run()