#! /usr/bin/env python

import numpy as np
from evo.core.trajectory import PosePath3D
from evo.core.metrics import APE, PoseRelation
from evo.core import trajectory, sync, metrics
from evo.tools import plot
from evo.tools import file_interface
import copy

# TODO(gogojjh): improve this implementation
def align_trajectory(traj_ref, traj_est):
    traj_est_aligned = copy.deepcopy(traj_est)
    align_R_t_s = traj_est_aligned.align(traj_ref, correct_scale=False, correct_only_scale=False)
    data = (traj_ref, traj_est_aligned)
    ape_metric = metrics.APE(pose_relation=metrics.PoseRelation.translation_part)
    ape_metric.process_data(data)
    return traj_ref, traj_est_aligned, ape_metric, align_R_t_s

def plot_aligned_traj(traj_ref, traj_est, ape_metric):
    ape_statistics = ape_metric.get_all_statistics()

    print("loading plot modules")
    from evo.tools import plot
    import matplotlib.pyplot as plt

    print("plotting")
    plot_collection = plot.PlotCollection("Example")
    # metric values
    fig_1 = plt.figure(figsize=(8, 8))
    plot.error_array(fig_1.gca(), ape_metric.error, statistics=ape_statistics,
                    name="APE", title=str(ape_metric))
    plot_collection.add_figure("raw", fig_1)

    # trajectory colormapped with error
    fig_2 = plt.figure(figsize=(8, 8))
    plot_mode = plot.PlotMode.xy
    ax = plot.prepare_axis(fig_2, plot_mode)
    plot.traj(ax, plot_mode, traj_ref, '--', 'gray', 'reference')
    plot.traj_colormap(ax, traj_est, ape_metric.error, plot_mode,
                    min_map=ape_statistics["min"],
                    max_map=ape_statistics["max"],
                    title="APE mapped onto trajectory")
    plot_collection.add_figure("traj (error)", fig_2)

    # trajectory colormapped with speed
    if hasattr(traj_ref, 'timestamps') and hasattr(traj_est, 'timestamps'):
        fig_3 = plt.figure(figsize=(8, 8))
        plot_mode = plot.PlotMode.xy
        ax = plot.prepare_axis(fig_3, plot_mode)
        speeds = [
            trajectory.calc_speed(traj_est.positions_xyz[i],
                                traj_est.positions_xyz[i + 1],
                                traj_est.timestamps[i], traj_est.timestamps[i + 1])
            for i in range(len(traj_est.positions_xyz) - 1)
        ]
        speeds.append(0)
        plot.traj(ax, plot_mode, traj_ref, '--', 'gray', 'reference')
        plot.traj_colormap(ax, traj_est, speeds, plot_mode, min_map=min(speeds),
                        max_map=max(speeds), title="speed mapped onto trajectory")
        fig_3.axes.append(ax)
        plot_collection.add_figure("traj (speed)", fig_3)

    plot_collection.show()    

if __name__ == "__main__":
    # Load reference and estimated trajectories
    traj_ref = file_interface.read_tum_trajectory_file("/Rocket_ssd/dataset/data_litevloc/traj_eval_data/map_merge_eval_data/groundtruth/traj/ucl_campus_s00000.txt")
    traj_est = file_interface.read_tum_trajectory_file("/Rocket_ssd/dataset/data_litevloc/traj_eval_data/map_merge_eval_data/algorithms/proposed/laptop/traj/ucl_campus_s00000.txt")

    traj_ref, traj_est_aligned, ape_metric = align_trajectory(traj_ref, traj_est)
    ape_statistics = ape_metric.get_all_statistics()    
    for key, value in ape_statistics.items():
        print("{}: {:.3f}".format(key, value))

    plot_aligned_traj(traj_ref, traj_est_aligned, ape_metric)