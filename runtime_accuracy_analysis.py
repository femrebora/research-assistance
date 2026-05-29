import matplotlib.pyplot as plt
import numpy as np


def generate_runtime_accuracy_analysis():
    # Set style
    plt.style.use('dark_background')
    plt.rcParams.update({'font.size': 12})

    # Data: Stride (X-axis) vs Runtime and Accuracy (Y-axes)
    stride = np.array([1, 2, 5, 10, 20, 50])
    runtime = 3600 / stride  # Simulated inverse relationship
    accuracy = np.array([0.98, 0.97, 0.95, 0.92, 0.85, 0.70]) # Simulated decay

    _fig, ax1 = plt.subplots(figsize=(10, 6))

    # Colorblind friendly colors from Plasma
    color_runtime = plt.cm.plasma(0.6)
    color_accuracy = plt.cm.plasma(0.9)

    # Plot Runtime
    ax1.set_xlabel('Trajectory Sampling Stride (Frames)', fontsize=14)
    ax1.set_ylabel('Execution Time (seconds)', color=color_runtime, fontsize=14)
    ax1.plot(stride, runtime, marker='o', color=color_runtime, linewidth=3, label='Runtime')
    ax1.tick_params(axis='y', labelcolor=color_runtime)
    ax1.set_xscale('log') # Log scale for stride often useful

    # Instantiate a second axes that shares the same x-axis
    ax2 = ax1.twinx()
    ax2.set_ylabel('Pocket Detection Accuracy', color=color_accuracy, fontsize=14)
    ax2.plot(stride, accuracy, marker='s', color=color_accuracy, linewidth=3, linestyle='--', label='Accuracy')
    ax2.tick_params(axis='y', labelcolor=color_accuracy)
    ax2.set_ylim(0.6, 1.05)

    # Title and Legend
    plt.title('Impact of Temporal Sampling on Efficiency and Accuracy', pad=20, fontsize=16)

    # Combined legend
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc='lower left', frameon=True, facecolor='#1e1e1e')

    # Grid
    ax1.grid(True, linestyle='--', alpha=0.2)

    # Save output
    plt.savefig('runtime_accuracy_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    generate_runtime_accuracy_analysis()
