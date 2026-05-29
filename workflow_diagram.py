import matplotlib.patches as patches
import matplotlib.pyplot as plt


def generate_workflow_diagram():
    # Set style
    plt.style.use('dark_background')
    _fig, ax = plt.subplots(figsize=(12, 6))

    # Define boxes (Phase, Label, X, Y)
    phases = [
        ("Phase I", "Trajectory Preprocessing\n& Frame Extraction", 0.05, 0.4),
        ("Phase II", "Static Pocket Prediction\n(Sequential Snapshots)", 0.3, 0.4),
        ("Phase III", "Longitudinal Clustering\n(Optimized DBSCAN)", 0.55, 0.4),
        ("Phase IV", "Pharmacophore-based\nEvaluation", 0.8, 0.4)
    ]

    box_width = 0.15
    box_height = 0.2

    # Draw boxes and text
    for i, (title, label, x, y) in enumerate(phases):
        # Create box
        rect = patches.FancyBboxPatch(
            (x, y), box_width, box_height,
            boxstyle="round,pad=0.02",
            edgecolor='#00ffcc', facecolor='#1e1e1e', linewidth=2
        )
        ax.add_patch(rect)

        # Add Title
        plt.text(x + box_width/2, y + box_height + 0.03, title,
                 ha='center', va='bottom', fontsize=12, fontweight='bold', color='#00ffcc')

        # Add Label
        plt.text(x + box_width/2, y + box_height/2, label,
                 ha='center', va='center', fontsize=10, color='white', wrap=True)

        # Draw Arrows
        if i < len(phases) - 1:
            next_x = phases[i+1][2]
            arrow = patches.FancyArrowPatch(
                (x + box_width, y + box_height/2),
                (next_x, y + box_height/2),
                connectionstyle="arc3,rad=0",
                arrowstyle='simple,head_width=8,head_length=10',
                color='#ffffff', mutation_scale=20
            )
            ax.add_patch(arrow)

    # Add descriptive title
    plt.title("PocketHunter: Computational Pipeline Workflow", fontsize=16, pad=30, color='#00ffcc')

    # Final touches
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')

    # Save output
    plt.savefig('workflow_diagram.png', dpi=300, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    generate_workflow_diagram()
