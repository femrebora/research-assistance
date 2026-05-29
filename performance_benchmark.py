import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def generate_performance_benchmark():
    # Set style
    plt.style.use('dark_background')
    plt.rcParams.update({'font.size': 12})

    # Simulate benchmarking data based on the "Layered Scoring" description
    np.random.seed(42)
    n_samples = 100

    data = {
        'Score': np.concatenate([
            np.random.normal(0.65, 0.1, n_samples), # Layer 0 Active
            np.random.normal(0.40, 0.1, n_samples), # Layer 0 Decoy
            np.random.normal(0.85, 0.08, n_samples),# Layer 1 Active
            np.random.normal(0.30, 0.12, n_samples) # Layer 1 Decoy
        ]),
        'Group': np.concatenate([
            ['Active'] * n_samples, ['Decoy'] * n_samples,
            ['Active'] * n_samples, ['Decoy'] * n_samples
        ]),
        'Scoring Layer': np.concatenate([
            ['Layer 0 (Baseline)'] * (2 * n_samples),
            ['Layer 1 (Pharmacophore)'] * (2 * n_samples)
        ])
    }

    df = pd.DataFrame(data)

    # Create the figure
    plt.figure(figsize=(10, 7))

    # Plot using a colorblind-friendly palette
    palette = sns.color_palette("viridis", 2)

    ax = sns.boxplot(x='Scoring Layer', y='Score', hue='Group', data=df,
                     palette=palette, linewidth=2, fliersize=4)

    # Customization
    plt.title('Discrimination Performance: Active vs. Decoy Ligands', pad=20, fontsize=16)
    plt.ylabel('Complementarity Score', fontsize=14)
    plt.xlabel('Scoring Methodology', fontsize=14)
    plt.legend(title='Ligand Type', frameon=True, facecolor='#1e1e1e', edgecolor='white')

    # Grid for readability
    ax.yaxis.grid(True, linestyle='--', alpha=0.3)
    ax.set_axisbelow(True)

    # Save output
    plt.savefig('performance_benchmark.png', dpi=300, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    generate_performance_benchmark()
