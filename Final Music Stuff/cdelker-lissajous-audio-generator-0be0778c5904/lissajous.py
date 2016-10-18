#!/usr/bin/env python
"""
Lissajous Function Generator

Generates stereo signals on audio port and generates XY (Lissajous) plot
of left channel vs. right channel.
"""

#-----------------------------------------------------------
# Copyright (c) 2012 Collin J. Delker
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met: 
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer. 
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution. 
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
#-----------------------------------------------------------
#
# NOTES:
#   This software requires the pyo python module:
#   http://code.google.com/p/pyo/
#
#   And the wx and matplotlib modules.
#
#-----------------------------------------------------------

#----------------------------------------------------------
# Imports
#----------------------------------------------------------
import pyo
import csv

import wx
import wx.lib.agw.floatspin as FS

import matplotlib
matplotlib.use('WXAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigCanvas


#----------------------------------------------------------
# Constants
#----------------------------------------------------------
__version__ = '0.1'

CH_CNT     = 3 * 2       # Number of total channels
PLAY_TIME  = 10 * 1000   # milliseconds to play each file in playback mode

FRAMERATE  = 200         # ms between plot updates. Increase if audio seems to skip.
RECBUFFER  = 0.01        # seconds to record and display in one plot frame. Should be >= lowest frequency.
PLT_COLOR  = 'yellow'

INIT_FREQ  = 400         # Initial Frequency
INIT_PHASE = 0           # Initial Phase
INIT_MUL   = 0.5         # Initial Amplitude


#----------------------------------------------------------
# Classes
#----------------------------------------------------------
class AudioControl(wx.Panel):
    """ Audio generator and controls class """

    def __init__(self, parent, *args, **kwargs):
        """ Initialize the audio streams and controls """
        wx.Panel.__init__(self, parent, *args, **kwargs)

        # Labels
        self.lblF = wx.StaticText( self, label='L Frequency' )
        self.lblAmp = wx.StaticText( self, label='L Amplitude' )
        self.lblPh = wx.StaticText( self, label='L Phase' )
        self.lblF2 = wx.StaticText( self, label='R Frequency' )
        self.lblAmp2 = wx.StaticText( self, label='R Amplitude' )
        self.lblPh2 = wx.StaticText( self, label='R Phase' )

        # Audio Controls
        self.freq         = []  # Frequency control list
        self.freq_idlist  = []  # Frequency spinner ID
        self.phase        = []  # Phase control list
        self.phase_idlist = []  # Phase spinner ID
        self.mul          = []  # Mul (amplitude) control list
        self.mul_idlist   = []  # Mul slider ID
        self.LR           = []  # Pan LR control list
        self.LR_idlist    = []  # Pan LR slider ID

        # Sizers
        self.main_sizer  = wx.BoxSizer( wx.VERTICAL )
        self.grid_sizerL = wx.GridSizer( rows=CH_CNT + 1, cols=3 )
        self.grid_sizerR = wx.GridSizer( rows=CH_CNT + 1, cols=3 )
        self.grid_sizerL.Add( self.lblF, 0, wx.ALL, 5 )
        self.grid_sizerL.Add( self.lblAmp, 0, wx.ALL, 5 )
        self.grid_sizerL.Add( self.lblPh, 0, wx.ALL, 5 )
        self.grid_sizerR.Add( self.lblF2, 0, wx.ALL, 5 )
        self.grid_sizerR.Add( self.lblAmp2, 0, wx.ALL, 5 )
        self.grid_sizerR.Add( self.lblPh2, 0, wx.ALL, 5 )
        self.main_sizer.Add( self.grid_sizerL, 0, wx.ALL, 0 )
        self.main_sizer.Add( self.grid_sizerR, 0, wx.ALL, 0 )
        self.SetSizer(self.main_sizer)
        self.main_sizer.Fit(self)

        self.init_audio()


    def init_audio(self):
        """ Initialize the audio streams and GUI controls """
        self.s = pyo.Server().boot()  # Start the pyo audio server

        self.func = []   # Function (Sine) objects
        Lsin_list = []
        Rsin_list = []

        for i in range(CH_CNT):
            # Left or right channel?
            sin_list = Lsin_list
            sizer = self.grid_sizerL
            if i > CH_CNT/2 - 1:
                sin_list = Rsin_list
                sizer = self.grid_sizerR

            # Start with only one sine per channel enabled
            mul = 0
            if i==0 or i==(CH_CNT/2):
                mul = INIT_MUL

            self.freq.append( FS.FloatSpin( self, digits=1, value=INIT_FREQ, min_val=20, max_val=20000, increment=1 ) )
            self.freq_idlist.append( self.freq[i].Id )
            self.freq[i].Bind( FS.EVT_FLOATSPIN, self.fspin )
            sizer.Add( self.freq[i], 0, wx.ALL, 5 )

            self.mul.append( wx.Slider( self, value=mul*100, minValue=0, maxValue=105, size=(100,20) ) )
            self.mul_idlist.append( self.mul[i].Id )
            self.mul[i].Bind( wx.EVT_SCROLL, self.mspin )
            sizer.Add( self.mul[i], 0, wx.ALL, 5 )

            self.phase.append( FS.FloatSpin( self, digits=1, value=INIT_PHASE, min_val=0, max_val=360, increment=1 ) )
            self.phase_idlist.append( self.phase[i].Id )
            self.phase[i].Bind( FS.EVT_FLOATSPIN, self.phspin )
            sizer.Add( self.phase[i], 0, wx.ALL, 5 )

            # Build the individual audio streams
            self.func.append( pyo.Sine( freq=INIT_FREQ, mul=mul ) )
            sin_list.append( self.func[i] )

        # Combine audio streams and set L/R pan
        self.Lch = pyo.Pan( pyo.Mix( Lsin_list ), pan=0, spread=0 )
        self.Rch = pyo.Pan( pyo.Mix( Rsin_list ), pan=1, spread=0 )
        self.Lch.setMul(0.5)  # To ensure no clipping
        self.Rch.setMul(0.5)
        self.Lch.out()        # Enables audio playback
        self.Rch.out()

        # Table for recording a short sample used for graph
        self.recording = False
        self.table     = pyo.NewTable( length=RECBUFFER, chnls=2 )
        self.trig_tbl  = pyo.TableRec( self.Lch+self.Rch, table=self.table )


    def start_buffer( self, enable ):
        """ Start saving audio to data table """
        if enable:
            self.trig_tbl.play()
        else:
            self.trig_tbl.stop()


    def get_buffer_data(self):
        """ Get X, Y lists in data table """
        Xdata = []
        Ydata = []
        for i in range(self.table.getSize()):
            point = self.table.get(i)
            Xdata.append( point[0] )
            Ydata.append( point[1] )
        return Xdata, Ydata


    def fspin( self, event ):
        """ Frequency spinner event """
        spinnerID = event.GetId()
        spinnerCtrl = self.FindWindowById( spinnerID )
        chidx = self.freq_idlist.index( spinnerID )
        self.func[chidx].setFreq( spinnerCtrl.GetValue() )


    def phspin( self, event ):
        """ Phase spinner event """
        self.reset_phase()


    def mspin( self, event ):
        """ Amplitude spinner event """
        ID = event.GetId()
        ctrl = self.FindWindowById( ID )
        chidx = self.mul_idlist.index( ID )
        self.func[chidx].setMul( float(ctrl.GetValue())/100 )


    def reset_phase(self):
        """ Reset the phase of all channels so they stay in sync """
        for f, ph in zip(self.func, self.phase):
            f.reset()
            f.setPhase( ph.GetValue()/360 )


    def enable_server(self, enable):
        """ Set audio server start/stop """
        if enable:
            self.s.start()
        else:
            self.s.stop()


    def record(self, filename='record.wav'):
        """ Start or stop recording to wav file """
        if not self.recording:
            self.s.recstart( filename )
            self.recording = True
        else:
            self.s.recstop()
            self.recording = False
            print 'Recording saved to', filename
        return self.recording


    def set_audio_params(self, funclist):
        """ Set the audio parameters from list of (freq, mul, phase) values """
        for idx, f in enumerate(funclist):
            self.freq[idx].SetValue(float(f[0]))
            self.mul[idx].SetValue(float(f[1])*100)
            self.phase[idx].SetValue(float(f[2])*360)
            self.func[idx].stop()
            self.func[idx].reset()
            self.func[idx].setFreq(float(f[0]))
            self.func[idx].setMul(float(f[1]))
            self.func[idx].setPhase(float(f[2]))
            self.func[idx].play()
        self.reset_phase()


    def get_audio_params(self):
        """ Return list of (freq, mul, phase) tuples for each channel """
        rows = [( func.freq, func.mul, func.phase ) for func in self.func]
        return rows


#----------------------------------------------------------
class mainFrame(wx.Frame):
    """Main Window Class"""
    def __init__(self, *args, **kwargs):
        """ Initialize the main window """
        wx.Frame.__init__(self, *args, **kwargs)

        self.audio = AudioControl(self)
        self.init_graph()
        self.init_frame()
        self.graphing = False
        self.toggle_graph()


    def init_graph(self):
        """ Initialize the graph """
        self.fig = Figure((4, 4), dpi=100)
        self.axes = self.fig.add_subplot(111)
        self.axes.set_axis_bgcolor('black')
        self.axes.set_title('XY', size=8)
        self.axes.set_xlim((-1,1))
        self.axes.set_ylim((-1,1))
        self.axes.xaxis.set_tick_params(labelsize=8)
        self.axes.yaxis.set_tick_params(labelsize=8)
        self.canvas = FigCanvas(self, -1, self.fig)
        self.plot_data = self.axes.plot( 0, 0, marker='o', markersize=2, color=PLT_COLOR, markeredgewidth=0 )[0]


    def init_frame(self):
        """ Initialize the main frame """

        # Buttons
        self.startButton = wx.Button(self, label='Start' )
        self.startButton.Bind(wx.EVT_BUTTON, self.start_press )
        self.recButton = wx.Button(self, label='Record WAV' )
        self.recButton.Bind(wx.EVT_BUTTON, self.rec_press )
        self.grphButton = wx.Button(self, label='Pause Graph' )
        self.grphButton.Bind(wx.EVT_BUTTON, self.graph_press )
        self.saveButton = wx.Button( self, label='Save Function' )
        self.saveButton.Bind( wx.EVT_BUTTON, self.save_press )
        self.loadButton = wx.Button( self, label='Load Function(s)' )
        self.loadButton.Bind( wx.EVT_BUTTON, self.load_press )

        # Sizers
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.button_sizer.Add( self.startButton, 0, wx.ALL, 5 )
        self.button_sizer.Add( self.recButton, 0, wx.ALL, 5 )
        self.button_sizer.Add( self.grphButton, 0, wx.ALL, 5 )
        self.button_sizer.Add( self.saveButton, 0, wx.ALL, 5 )
        self.button_sizer.Add( self.loadButton, 0, wx.ALL, 5 )
        self.top_sizer.Add( self.canvas, 0, flag=wx.LEFT | wx.TOP | wx.GROW )
        self.top_sizer.Add( self.audio, 0, wx.ALL, 5 )
        self.main_sizer.Add( self.top_sizer, 0, wx.ALL, 0 )
        self.main_sizer.Add( self.button_sizer, 0, wx.ALL, 0 )
        self.SetSizer(self.main_sizer)
        self.main_sizer.Fit(self)

        # Timer for playing multiple files
        self.multifile_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_multifile_timer, self.multifile_timer)

        # Timer for refreshing graph
        self.redraw_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_redraw_timer, self.redraw_timer)
        self.redraw_timer.Start(FRAMERATE)


    def refresh_plot(self, Xdata, Ydata ):
        """ Refresh the plot """
        self.plot_data.set_xdata( Xdata )
        self.plot_data.set_ydata( Ydata )
        self.canvas.draw()


    def save_press( self, event ):
        """ Save the settings to a file """
        dirname = ''
        dlg = wx.FileDialog(self, "Save File", dirname, "", "*.*", wx.SAVE)
        if dlg.ShowModal() == wx.ID_OK:
            f = open(dlg.GetPath(), 'w')
            writer = csv.writer(f, delimiter=',')
            writer.writerows( self.audio.get_audio_params() )
            print 'File written'
            f.close()
        dlg.Destroy()


    def load_press( self, event ):
        """ Load settings from a file.

        If multiple files selected, they are placed in queue and
        each one is played for PLAY_TIME seconds.
        """
        dlg = wx.FileDialog(self, "Load File(s)", '.', "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.filelist = dlg.GetPaths()

            if len(self.filelist) > 1:
                # Multiple files selected, start the playback timer
                self.multifile_timer.Start(PLAY_TIME)
                print len(self.filelist), 'files queued.'

            self.start_next_file()
        dlg.Destroy()


    def rec_press( self, event ):
        """ Record audio to WAV file """
        recording = self.audio.record()
        if recording:
            self.recButton.SetLabel('Record Stop')
        else:
            self.recButton.SetLabel('Record Start')


    def start_press(self, event):
        """ Start or stop the audio playback """
        if self.startButton.GetLabel() == 'Start':
            self.startButton.SetLabel('Stop')
            self.audio.enable_server(True)
        else:
            self.startButton.SetLabel('Start')
            self.audio.enable_server(False)


    def start_next_file( self ):
        """ Start playing the next file in the queue """
        if len(self.filelist) > 0:
            fname = self.filelist.pop(0)
            f = open(fname, 'r')
            reader = csv.reader(f, delimiter=',')
            self.audio.set_audio_params( reader )
            print 'File loaded', fname
            f.close()


    def on_redraw_timer(self, event):
        """ Timer event to redraw the graph """
        if self.graphing:
            Xdata, Ydata = self.audio.get_buffer_data()
            self.audio.start_buffer(True)
            self.refresh_plot( Xdata, Ydata )


    def on_multifile_timer(self, event):
        """ Timer event to start the next file in queue """
        if len(self.filelist) <= 0:
            self.multifile_timer.Stop()
            self.audio.enable_server(False)
            self.startButton.SetLabel('Start')
            print 'Playback complete'
        else:
            self.start_next_file()


    def graph_press(self, event):
        """ Graph button press """
        self.toggle_graph()


    def toggle_graph( self ):
        """ Toggle the graph on and off """
        if self.graphing == False:
            self.graphing = True
            self.audio.start_buffer(True)
            self.grphButton.SetLabel('Pause Graph')
        else:
            self.graphing = False
            self.audio.start_buffer(False)
            self.grphButton.SetLabel('Start Graph')


#----------------------------------------------------------
class mainApp(wx.App):
    """Main Application Class"""
    def OnInit(self):
        frame = mainFrame(None, title="Lissajous Audio Generator" )
        frame.Show()
        self.SetTopWindow(frame)
        return True


#----------------------------------------------------------
# Main Program Entry
#----------------------------------------------------------
if __name__ == "__main__":
    app = mainApp(redirect=False)
    app.MainLoop()
