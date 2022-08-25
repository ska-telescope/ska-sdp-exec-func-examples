import numpy as np
import argparse
import os
import aoflagger
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import ListedColormap
from time import process_time

parser = argparse.ArgumentParser(description='Project location')
parser.add_argument('--projname', type=str, nargs=1, help='name of the experiment')
parser.add_argument('--rfi_exists', default=False, action='store_true')
args = parser.parse_args()


directory = args.projname
mydir = directory[0]
flagger = aoflagger.AOFlagger()

def accuracy_measure(myflags, rfi_abs, path):
    num_times = myflags.shape[0]
    num_freqs = myflags.shape[1]
    tp = 0
    tn = 0
    fp = 0
    fn = 0
    for i in range(num_times):
      for j in range(num_freqs):
        if myflags[i][j] == 0 and rfi_abs[i][j] == 0:
           tn = tn + 1
        if myflags[i][j] == 0 and rfi_abs[i][j] > 0:
           fn = fn + 1
        if myflags[i][j] == 1 and rfi_abs[i][j] == 0:
           fp = fp + 1
        if myflags[i][j] == 1 and rfi_abs[i][j] > 0:
           tp = tp + 1
    f1_score = tp / (tp + 0.5 * (fp + fn))
    mattew = (tp * tn - fp * fn)/np.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    f = open(path + "/aof_performance.txt", "a")
    f.write("True Positives: " + str(tp) + "\n")
    f.write("False Positives: " + str(fp) + "\n")
    f.write("True Negatives: " + str(tn) + "\n")
    f.write("False Negatives: " + str(fn) + "\n")
    f.write("F1-score: " + str(f1_score) + "\n")
    f.write("Mattew's correlation: " + str(mattew) + "\n")
    f.close()
    return tp, fp, tn, fn, f1_score, mattew


def visualiser(mydata,  mypath):
    cmap = sns.cubehelix_palette(start=1.8, rot=1.1, light=0.7, n_colors=2)
    plt.figure()
    ax = sns.heatmap(mydata, cmap=ListedColormap(cmap), cbar_kws={"ticks": [0, 1]})
    title = "flags by AOFlagger " 
    plt.title(title)
    plt.xlabel('channels')
    plt.ylabel('time')
    filename = mypath + "/aof_flags.png"
    plt.savefig(filename)
    plt.close()


total_process_time = 0
tp_total = 0
tn_total = 0
fp_total = 0
fn_total = 0

observation_index = 0


for dir1 in os.listdir(mydir):
     print(observation_index)
     for dir2 in os.listdir(mydir + "/" + dir1):
        path = mydir + "/" + dir1 + "/" +dir2 + "/"
        file = path + "visibilities.npy"
        vis = np.abs(np.load(file))
        visshape = vis.shape
        num_times = visshape[0]
        num_freqs = visshape[1]
        aopath = flagger.find_strategy_file(aoflagger.TelescopeId.Generic)
        strategy = flagger.load_strategy_file(aopath)
        data = flagger.make_image_set(num_times, num_freqs, 1)
        data.set_image_buffer(0, np.transpose(vis))
        t1_begin = process_time()
        flags = strategy.run(data)
        t1_end = process_time()
        total_process_time = total_process_time + (t1_end - t1_begin)
        flagvalues = flags.get_buffer()
        visualiser(np.transpose(flagvalues), path)
        f = open(path + "/aof_performance.txt", "a")
        f.write("processing time: " + str(t1_end - t1_begin) + "\n")   
        myflags = np.transpose(flagvalues)
        ratio = np.sum(np.sum(myflags))/(num_times * num_freqs)        
        f.write("ratio flagged: " + str(ratio) + "\n")
        f.close()
        np.save(path + "/aof_flags", myflags)
        visualiser(myflags, path)
        if args.rfi_exists==True:
           myrfi = np.load(path + "rfi.npy")
           tp, fp, tn, fn, f1_score, mattew = accuracy_measure(myflags, myrfi, path)
           tp_total = tp_total + tp
           tn_total = tn_total + tn
           fp_total = fp_total + fp
           fn_total = fn_total + fn

if args.rfi_exists == True:
   f = open(args.projname[0] + "/aof_total_performance.txt", "a")
   f1_sc_tot = tp_total / (tp_total + 0.5 * (fp_total + fn_total))
   mattew_tot = (tp_total * tn_total - fp_total * fn_total)/np.sqrt(float((tp_total + fp_total) * (tp_total + fn_total) * (tn_total + fp_total) * (tn_total + fn_total)))  
   f.write("True Positive: " + str(tp_total) + "\n")
   f.write("True Negative: " + str(tn_total) + "\n")   
   f.write("False Positive: " + str(fp_total) + "\n")
   f.write("False Negative: " + str(fn_total) + "\n")
   f.write("F1 score: " + str(f1_sc_tot) + "\n")
   f.write("Mattew's correlation: " + str(mattew_tot) + "\n")
   f.write("Total Processing Time: " + str(total_process_time) + "\n" )
   f.close()
