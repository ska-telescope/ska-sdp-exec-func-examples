from ska_sdp_func import twosm_rfi_flagger
import casacore.tables as tables
import numpy as np
import argparse
import os
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import ListedColormap
from time import process_time

parser = argparse.ArgumentParser(description='MeasurementSets locations')
parser.add_argument('--vis', type=str, nargs=1, help='the location for the visibility MeasurementSet'
                                                     ' (raw visibilities or combined with RFI')
parser.add_argument('--rfi', type=str, nargs=1, required=False, help='the location for the RFI'
                                                                     ' MeasurementSet (if known)')
parser.add_argument('--thresholds', type=float, nargs=2, help='thresholds for time and frequency dimensions')
parser.add_argument('--projname', type=str, nargs=1, help='name of the experiment')

args = parser.parse_args()

vis_table = tables.table(args.vis)
if args.rfi is not None:
    rfi_table = tables.table(args.rfi)

thresholds = np.array(args.thresholds, dtype=np.float32)

num_rows = vis_table.nrows()

print("number of rows: ", num_rows)
vis_one_row = vis_table.getcol('DATA', 0, 1)
num_freqs = vis_one_row.shape[1]
num_pols = vis_one_row.shape[2]

antenna1 = vis_table.getcol('ANTENNA1', 0, num_rows)
antenna_ids = np.unique(antenna1)

num_antennas = len(antenna_ids)
num_baselines = int(num_antennas * (num_antennas + 1)/2)
num_times = int( num_rows/num_baselines)

print(num_times)
print(num_freqs)
print(num_pols)
print(antenna_ids)

field_id = vis_table.getcol('FIELD_ID', 0, num_times, num_baselines)
scan_number = vis_table.getcol('SCAN_NUMBER', 0, num_times, num_baselines)
changes = [0]

for i in range(1,num_times):
    if field_id[i] != field_id[i - 1] or scan_number[i] != scan_number[i - 1]:
        changes.append(i)

changes_arr = np.array(changes)
changes_arr = np.append(changes_arr, [num_times])
print(changes_arr)

if not os.path.exists(args.projname[0]):
    k = 0
    os.mkdir(args.projname[0])
    for c in range(len(changes_arr) - 1):
        new_observation_folder = args.projname[0] + "/observation" + str(k)
        k = k + 1
        os.mkdir(new_observation_folder)
        for ant in antenna_ids:
            for pol in range(num_pols):
                new_experiment = new_observation_folder + "/experiment_ant" + str(ant) + "_p" + str(pol)
                os.mkdir(new_experiment)
else:
    print("Path already exists!")


def accuracy_measure(myflags, rfi_abs, path):
    num_times = flags.shape[0]
    num_freqs = flags.shape[1]
    tp = 0
    tn = 0
    fp = 0
    fn = 0
    for i in range(num_times):
      for j in range(num_freqs):
        if flags[i][j] == 0 and rfi_abs[i][j] == 0:
           tn = tn + 1
        if flags[i][j] == 0 and rfi_abs[i][j] > 0:
           fn = fn + 1
        if flags[i][j] == 1 and rfi_abs[i][j] == 0:
           fp = fp + 1
        if flags[i][j] == 1 and rfi_abs[i][j] > 0:
           tp = tp + 1
    f1_score = tp / (tp + 0.5 * (fp + fn))
    mattew = (tp * tn - fp * fn)/np.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    f = open(path + "/performance.txt", "a")
    f.write("True Positives: " + str(tp) + "\n")
    f.write("False Positives: " + str(fp) + "\n")
    f.write("True Negatives: " + str(tn) + "\n")
    f.write("False Negatives: " + str(fn) + "\n")
    f.write("F1-score: " + str(f1_score) + "\n")
    f.write("Mattew's correlation: " + str(mattew) + "\n")
    f.close()
    return tp, fp, tn, fn, f1_score, mattew



def visualiser(data, thresholdz, typeexp, path):
    if typeexp == "flag":
        cmap = sns.cubehelix_palette(start=1.8, rot=1.1, light=0.7, n_colors=2)
        plt.figure()
        ax = sns.heatmap(data, cmap=ListedColormap(cmap), cbar_kws={"ticks": [0, 1]})
        title = "flags by 2SM for thresholds " + str(thresholdz[0]) + ", " + str(thresholdz[1])
        plt.title(title)
        plt.xlabel('channels')
        plt.ylabel('time')
        filename = path + "/flags.png"
        plt.savefig(filename)
        plt.close()
    if typeexp == "vis":
        cmap = sns.cubehelix_palette(start=2.8, rot=1.6, light=0.9, n_colors=1000)
        plt.figure()
        ax = sns.heatmap(data, cmap=ListedColormap(cmap))
        plt.title("visibilities")
        plt.xlabel('channels')
        plt.ylabel('time')
        filename = path + "/vis.png"
        plt.savefig(filename)
        plt.close()

total_process_time = 0
tp_total = 0
tn_total = 0
fp_total = 0
fn_total = 0

for i in range(1, len(changes_arr)):
    print(i)
    length = changes_arr[i] - changes_arr[i - 1]
    for ant in antenna_ids:
        begin = num_baselines * changes_arr[i - 1] + ant
        vis = vis_table.getcol('DATA', begin, length, num_baselines)
        if args.rfi is not None:
            rfi = rfi_table.getcol('DATA', begin, length, num_baselines)
            sig = vis + rfi
        else:
            sig = vis
        for pol in range(num_pols):
            mysig = np.ascontiguousarray(np.squeeze(sig[:, :, pol]))
            if args.rfi is not None:
               myrfi = np.abs(np.squeeze(rfi[:, :, pol]))
            flags = np.zeros([length, num_freqs], dtype=np.int32)
            t1_begin = process_time() 
            twosm_rfi_flagger(mysig, thresholds, flags)
            t1_end = process_time()
            total_process_time = total_process_time + (t1_end - t1_begin)
            path = args.projname[0] + "/observation" + str(i - 1) + \
                   "/experiment_ant" + str(ant) + "_p" + str(pol)
            np.save(path + "/visibilities", np.abs(mysig))
            if args.rfi is not None:
               np.save(path + "/rfi", myrfi)
            f = open(path + "/performance.txt", "a")
            f.write("processing time: " + str(t1_end - t1_begin) + "\n")   
            ratio = np.sum(np.sum(flags))/(num_times * num_freqs)        
            f.write("ratio flagged: " + str(ratio) + "\n")
            f.close()
            visualiser(flags, thresholds, "flag", path)
            visualiser(abs(mysig), thresholds, "vis", path)
            if args.rfi is not None:
               tp, fp, tn, fn, f1_score, mattew = accuracy_measure(flags, myrfi, path)
               tp_total = tp_total + tp
               tn_total = tn_total + tn
               fp_total = fp_total + fp
               fn_total = fn_total + fn

if args.rfi is not None:
   f = open(args.projname[0] + "_total_performance.txt", "a")
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
