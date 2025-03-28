# This is for the notebook to reload external python modules

from IPython.display import Markdown, display
import typing
import matplotlib.pyplot as plt
import sys
from dataclasses import dataclass

sys.path.insert(0, "../src")
import skadipy.safety
import skadipy.toolbox
import skadipy.allocator
import skadipy.actuator
import skadipy.allocator.reference_filters as rf

from skadipy.plotting.nice_plots import *

from save_data import *

# Importing the necessary modules

# Setting the plot style
plt.rcParams["text.usetex"] = True
plt.rcParams["mathtext.fontset"] = "stix"
plt.rcParams["font.family"] = "STIXGeneral"

# Increase the font size for labels
plt.rcParams.update({"font.size": 18})
# keep the font size for ticks the same
plt.rcParams.update({"xtick.labelsize": 10})
plt.rcParams.update({"ytick.labelsize": 10})
# keep the font size for legend the same
plt.rcParams.update({"legend.fontsize": 10})


# Creating the vessel
tunnel = skadipy.actuator.Fixed(
    position=skadipy.toolbox.Point([0.3875, 0.0, 0.0]),
    orientation=skadipy.toolbox.Quaternion(axis=(0.0, 0.0, 1.0), radians=np.pi / 2.0),
    extra_attributes={
        "rate_limit": 1.0,
        "saturation_limit": 1.0,
        "limits": [-1.0, 1.0],
    },
)
voithschneider_port = skadipy.actuator.Azimuth(
    position=skadipy.toolbox.Point([-0.4574, -0.055, 0.0]),
    extra_attributes={
        "rate_limit": 1.0,
        "saturation_limit": 1.0,
        "reference_angle": np.pi / 4.0,
        "limits": [0.0, 1.0],
    },
)
voithschneider_starboard = skadipy.actuator.Azimuth(
    position=skadipy.toolbox.Point([-0.4547, 0.055, 0.0]),
    extra_attributes={
        "rate_limit": 1.0,
        "saturation_limit": 1.0,
        "reference_angle": -np.pi / 4.0,
        "limits": [0.0, 1.0],
    },
)

ma_bow_port = skadipy.actuator.Azimuth(
    position=skadipy.toolbox.Point([1.8, -0.8, 0.0]),
    orientation=skadipy.toolbox.Quaternion(
        axis=(0.0, 0.0, 1.0), angle=(3 * np.pi / 4.0)
    ),
    extra_attributes={
        "rate_limit": 0.1,
        "saturation_limit": 10.0,
        "limits": [0.0, 1.0],
        "reference_angle": 0.0,
    },
)
ma_bow_starboard = skadipy.actuator.Azimuth(
    position=skadipy.toolbox.Point([1.8, 0.8, 0.0]),
    orientation=skadipy.toolbox.Quaternion(
        axis=(0.0, 0.0, 1.0), angle=(-3 * np.pi / 4.0)
    ),
    extra_attributes={
        "rate_limit": 0.1,
        "saturation_limit": 10.0,
        "limits": [0.0, 1.0],
        "reference_angle": 0.0,
    },
)
ma_aft_port = skadipy.actuator.Azimuth(
    position=skadipy.toolbox.Point([-1.8, -0.8, 0.0]),
    orientation=skadipy.toolbox.Quaternion(
        axis=(0.0, 0.0, 1.0), angle=(np.pi / 4.0)),
    extra_attributes={
        "rate_limit": 0.1,
        "saturation_limit": 10.0,
        "limits": [0.0, 1.0],
        "reference_angle": 0.0,
    },
)
ma_aft_starboard = skadipy.actuator.Azimuth(
    position=skadipy.toolbox.Point([-1.8, 0.8, 0.0]),
    orientation=skadipy.toolbox.Quaternion(
        axis=(0.0, 0.0, 1.0), angle=(- np.pi / 4.0)),
    extra_attributes={
        "rate_limit": 0.1,
        "saturation_limit": 10.0,
        "limits": [0.0, 1.0],
        "reference_angle": 0.0,
    },
)


def generate_spiral_dataset(
    num_points: int, num_turns: float, k: float = 1.0
) -> np.ndarray:
    """
    Generate a dataset of points on a spiral.

    :param num_points: The number of points to generate.
    :param num_turns: The number of turns to make.
    :param k: The scaling factor for the spiral.
    """
    angles = np.linspace(0, 2 * np.pi * num_turns, num_points)
    radii = np.linspace(0, 1, num_points)
    return np.column_stack((np.cos(angles) * radii, np.sin(angles) * radii)) * k


def gen_clipped_sin(
    n: int,
    amplitude: float,
    period: float,
    phase: float,
    offset: float,
    clip_n: float = -1.0,
    clip_p: float = 1.0,
):
    """
    Generate a clipped sine wave.

    :param n: The number of points to generate.
    :param amplitude: The amplitude of the sine wave.
    :param period: The period of the sine wave.
    :param phase: The phase of the sine wave.
    :param offset: The offset of the sine wave.
    :param clip_n: The negative clipping value.
    :param clip_p: The positive clipping value.

    :return: The clipped sine wave.
    """
    return np.clip(
        amplitude * np.sin(np.linspace(0, 2 * np.pi * period, n) + phase) + offset,
        clip_n,
        clip_p,
    )


@dataclass
class TestResults:
    xi_out_hist: np.ndarray
    xi_desired_hist: np.ndarray
    theta_hist: np.ndarray
    tau_desired_hist: np.ndarray

    def __init__(self):
        pass


def run_tests2(
    tau_cmd: np.ndarray = None,
    d_tau_cmd: np.ndarray = None,
    allocators: typing.List[skadipy.allocator.AllocatorBase] = None,
) -> TestResults:
    """
    Run the tests for the given allocator and input forces.

    :param tau_cmd: The input forces to the system. This is a 2D array with shape (N, 6), where N is the number of samples.
    :param d_tau_cmd: The derivative of the input forces to the system. This is a 2D array with shape (N, 6), where N is the number of samples.
    :param allocators: The list of allocator to test.
    :return: A tuple with the following elements:
        - xi_hist: A 3D array with shape (len(allocator), N, n), where n is the number of inputs to the allocator.
        - theta_hist: A 3D array with shape (len(allocator), N, q), where q is the number of outputs from the allocator.
        - tau_hist: A 3D array with shape (len(allocator), N, 6), where 6 is the number of force components.
    """
    results = TestResults()

    # get the number of samples
    N = tau_cmd.shape[0]

    # Prepare the allocator
    for i in allocators:
        i.compute_configuration_matrix()

    # Get the first allocator's B matrix and compute the number of inputs and outputs
    dof_indices = [i.value for i in allocators[0].force_torque_components]
    B = allocators[0]._b_matrix[dof_indices, :]
    n = B.shape[1]
    q = B.shape[1] - B.shape[0]
    del B, dof_indices

    # Prepare the history arrays
    results.xi_out_hist = np.zeros((len(allocators), N, n))
    results.xi_desired_hist = np.zeros((len(allocators), N, n))
    results.theta_hist = np.zeros((len(allocators), N, q))
    results.tau_desired_hist = np.zeros((len(allocators), N, 6))

    # Run the tests
    for i, allocator in enumerate(allocators):
        for j in range(N):

            kwargs = {}
            kwargs["tau"] = np.reshape(tau_cmd[j], (6, 1))
            if d_tau_cmd is not None:
                kwargs["d_tau"] = np.reshape(d_tau_cmd[j], (6, 1))

            if isinstance(allocator, rf.ReferenceFilterBase):
                pass

            xi_out, theta = allocator.allocate(**kwargs)

            if isinstance(allocator, rf.ReferenceFilterBase):

                results.xi_out_hist[i, j, :] = xi_out.flatten()

                results.xi_desired_hist[i, j, :] = allocator._xi_desired.flatten()

                if theta is not None:
                    results.theta_hist[i, j, :] = theta.flatten()

                results.tau_desired_hist[i, j, :] = allocator.allocated.flatten()

            else:
                results.xi_out_hist[i, j, :] = np.array(xi_out, dtype=float).flatten()
                results.tau_desired_hist[i, j, :] = allocator.allocated.flatten()

    # Return the results
    return results


def run_tests(
    tau_cmd: np.ndarray = None,
    d_tau_cmd: np.ndarray = None,
    allocators: typing.List[skadipy.allocator.AllocatorBase] = None,
) -> typing.Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Run the tests for the given allocator and input forces.

    :param tau_cmd: The input forces to the system. This is a 2D array with shape (N, 6), where N is the number of samples.
    :param d_tau_cmd: The derivative of the input forces to the system. This is a 2D array with shape (N, 6), where N is the number of samples.
    :param allocators: The list of allocator to test.
    :return: A tuple with the following elements:
        - xi_hist: A 3D array with shape (len(allocator), N, n), where n is the number of inputs to the allocator.
        - theta_hist: A 3D array with shape (len(allocator), N, q), where q is the number of outputs from the allocator.
        - tau_hist: A 3D array with shape (len(allocator), N, 6), where 6 is the number of force components.
    """
    # get the number of samples
    N = tau_cmd.shape[0]

    # Prepare the allocator
    for i in allocators:
        i.compute_configuration_matrix()

    # Get the first allocator's B matrix and compute the number of inputs and outputs
    dof_indices = [i.value for i in allocators[0].force_torque_components]
    B = allocators[0]._b_matrix[dof_indices, :]
    n = B.shape[1]
    q = B.shape[1] - B.shape[0]
    del B, dof_indices

    # Prepare the history arrays
    xi_hist = np.zeros((len(allocators), N, n))
    xi_desired_hist = np.zeros((len(allocators), N, n))
    theta_hist = np.zeros((len(allocators), N, q))
    tau_desired_hist = np.zeros((len(allocators), N, 6))

    # Run the tests
    for i, allocator in enumerate(allocators):
        for j in range(N):

            kwargs = {}
            kwargs["tau"] = np.reshape(tau_cmd[j], (6, 1))
            if d_tau_cmd is not None:
                kwargs["d_tau"] = np.reshape(d_tau_cmd[j], (6, 1))

            xi_desired, theta = allocator.allocate(**kwargs)

            if isinstance(allocator, rf.ReferenceFilterBase):
                xi = allocator._xi
                xi_desired_hist[i, j, :] = xi_desired.flatten()
                if theta is not None:
                    theta_hist[i, j, :] = theta.flatten()
                tau_desired_hist[i, j, :] = allocator.allocated.flatten()

                xi_hist[i, j, :] = xi.flatten()

            else:
                xi_desired_hist[i, j, :] = np.array(xi_desired, dtype=float).flatten()
                tau_desired_hist[i, j, :] = allocator.allocated.flatten()

    # Return the results
    return (xi_desired_hist, theta_hist, tau_desired_hist)


def plot_histories(tau_cmd, tau_alloc, indices=[0, 1, 5], dt=1.0):
    labels = [r"$F_x$", r"$F_y$", r"$F_z$", r"$M_x$", r"$M_y$", r"$M_z$"]

    fig, ax = plt.subplots(len(indices), 1, figsize=(8, 8))

    fig.tight_layout(pad=1.5)

    t = np.linspace(0, dt * len(tau_cmd), len(tau_cmd))

    for i in range(len(indices)):
        ax[i].plot(
            t,
            tau_cmd[:, indices[i]],
            label="Input " + labels[indices[i]],
            linewidth=1,
            linestyle="-",
            color="black",
        )

        for j in range(len(tau_alloc)):
            ax[i].plot(
                t,
                tau_alloc[j][:, indices[i]],
                label="Output " + labels[indices[i]],
                linewidth=1,
                linestyle="-",
                color=colors[j],
            )

        ax[i].set_xlabel("Time [s]")
        ax[i].set_ylabel(labels[indices[i]] + " [N]")

        ax[i].grid(True)
        ax[i].legend()

    return fig, ax


def plot_2d_allocation(
    tau_cmd: np.ndarray,
    allocators: typing.List[skadipy.allocator.AllocatorBase],
    tau_hist: np.ndarray,
    dt=1.0,
    npoints=150,
):

    fig, ax = plt.subplots(2, 1, height_ratios=[4, 1], figsize=(8, 8))

    t = np.linspace(0, dt * len(tau_cmd), len(tau_cmd))

    fig.tight_layout(pad=1.5)

    step_size = len(tau_cmd) // npoints

    ax[0].scatter(
        tau_cmd[::step_size, 0],
        tau_cmd[::step_size, 1],
        s=5,
        label="Input forces",
        color="black",
    )

    for allocator, F, color in zip(allocators, tau_hist, colors):
        ax[0].scatter(F[::step_size, 0], F[::step_size, 1], s=5, color=color)
        for i in range(0, len(tau_cmd), step_size):
            ax[0].plot(
                [tau_cmd[i, 0], F[i, 0]],
                [tau_cmd[i, 1], F[i, 1]],
                "--",
                color=color,
                lw=0.5,
                label="_nolegend_",
            )

    ax[0].grid(True)
    ax[0].axis("equal")
    ax[0].legend()
    ax[0].set_xlabel(r"$F_x$ [N]")
    ax[0].set_ylabel(r"$F_y$ [N]")

    ax[1].plot(
        t,
        tau_cmd[:, 5],
        label=r"Input $M_z$",
        linewidth=1,
        linestyle="-",
        color="black",
    )

    for j in range(len(tau_hist)):
        ax[1].plot(
            t,
            tau_hist[j][:, 5],
            label=r"Output $M_z$",
            linewidth=1,
            linestyle="-",
            color=colors[j],
        )

    ax[1].set_xlabel("Time [s]")
    ax[1].set_ylabel("$M_z$ [Nm]")

    ax[1].grid(True)
    ax[1].legend()

    return fig, ax


def plot_angles(xi_hist, dt=1.0):
    angles = []

    t = np.linspace(0, dt * len(xi_hist[0]), len(xi_hist[0]))

    for xi in xi_hist:
        a = np.empty((len(xi), 2))
        for i, u in enumerate(xi):
            a2 = np.arctan2(u[2], u[1])
            a3 = np.arctan2(u[4], u[3])
            a[i] = np.array([a3])
        angles.append(a)

    for _, angle in enumerate(angles):
        angle[0:3, 0] = None

    fig, ax = plt.subplots(1, 1, figsize=(8, 8))
    for i, angle in enumerate(angles):
        ax.plot(t, np.degrees(angle[:, 0]), color=colors[i])

    ax.set_xlabel("Time [s]")
    ax.set_ylabel(r"$\alpha_1$ [Deg]")
    ax.grid(True)

    return fig, ax


def plot_angles_reference_filter(xi_hist, xi_desired_hist, dt=1.0):
    angles = []
    angles_desired = []

    t = np.linspace(0, dt * len(xi_hist[0]), len(xi_hist[0]))

    for xi, xi_d in zip(xi_hist, xi_desired_hist):
        a = np.empty((len(xi), 2))
        a_d = np.empty((len(xi), 2))
        for i, (u, u_d) in enumerate(zip(xi, xi_d)):
            un = u[3:5] / (np.linalg.norm(u[3:5]) + 1e-5)
            a[i] = np.array([np.arctan2(un[1], un[0])])
            und = u_d[3:5] / (np.linalg.norm(u_d[3:5]) + 1e-5)
            a_d[i] = np.array([np.arctan2(und[1], und[0])])

        angles.append(a)

        angles_desired.append(a_d)

    for _, angle in enumerate(angles):
        angle[0:3, 0] = None

    fig, ax = plt.subplots(1, 1, figsize=(8, 8))
    for i, (angle, angle_desired) in enumerate(zip(angles, angles_desired)):
        ax.plot(t, np.degrees(np.unwrap(angle[:, 0])), color=colors[i])
        ax.plot(
            t, np.degrees(np.unwrap(angle_desired[:, 0])), "-.", color=darker_colors[i]
        )

    ax.set_xlabel("Time [s]")
    ax.set_ylabel(r"$\alpha_1$ [Deg]")
    ax.grid(True)

    return fig, ax


def plot_thruster_forces(xi_hist, dt=1.0):

    fig, ax = plt.subplots(3, 1, figsize=(8, 8))

    t = np.linspace(0, dt * len(xi_hist[0]), len(xi_hist[0]))

    fig.tight_layout(pad=1.5)
    for i, xi in enumerate(xi_hist):
        F_0 = xi[:, 0]
        F_1 = np.linalg.norm(xi[:, 1:2], axis=1)
        F_2 = np.linalg.norm(xi[:, 2:3], axis=1)
        ax[0].plot(t, F_0, color=colors[i])
        ax[1].plot(t, F_1, color=colors[i])
        ax[2].plot(t, F_2, color=colors[i])

        ax[0].set_ylabel("Tunnel [N]")
        ax[1].set_ylabel("Port [N]")
        ax[2].set_ylabel("Starboard [N]")
        for j in range(3):
            ax[j].set_xlabel("Time [s]")
            ax[j].grid(True)

    return fig, ax


def plot_thruster_forces_reference_filter(xi_hist, xi_desired_hist, dt=1.0):

    fig, ax = plt.subplots(3, 1, figsize=(8, 8))

    t = np.linspace(0, dt * len(xi_hist[0]), len(xi_hist[0]))

    fig.tight_layout(pad=1.5)
    for i, (xi, xi_d) in enumerate(zip(xi_hist, xi_desired_hist)):
        F_0 = xi[:, 0]
        F_1 = np.linalg.norm(xi[:, 1:2], axis=1)
        F_2 = np.linalg.norm(xi[:, 3:4], axis=1)

        F_d0 = xi_d[:, 0]
        F_d1 = np.linalg.norm(xi_d[:, 1:2], axis=1)
        F_d2 = np.linalg.norm(xi_d[:, 3:4], axis=1)

        ax[0].plot(t, F_0, "-", color=colors[i])
        ax[0].plot(t, F_d0, "--", color=darker_colors[i])
        ax[1].plot(t, F_1, "-", color=colors[i])
        ax[1].plot(t, F_d1, "--", color=darker_colors[i])
        ax[2].plot(t, F_2, "-", color=colors[i])
        ax[2].plot(t, F_d2, "--", color=darker_colors[i])

        ax[0].set_ylabel("Tunnel [N]")
        ax[1].set_ylabel("Port [N]")
        ax[2].set_ylabel("Starboard [N]")
        for j in range(3):
            ax[j].set_xlabel("Time [s]")
            ax[j].grid(True)

    return fig, ax


def plot_theta_histories(theta_hist, dt=1.0):

    fig, ax = plt.subplots(2, 1, figsize=(6, 4), height_ratios=[1, 1])

    t = np.linspace(0, dt * len(theta_hist[0]), len(theta_hist[0]))

    for i in range(theta_hist.shape[0]):
        ax[0].plot(t, theta_hist[i, :, 0], "-", color=colors[i])
    ax[0].set_ylabel(r"$\theta_1$")

    for i in range(theta_hist.shape[0]):
        ax[1].plot(t, theta_hist[i, :, 1], "-", color=colors[i])
    ax[1].set_ylabel(r"$\theta_2$")

    for a in ax:
        a.set_xlabel("Time [s]")
        a.grid(True)

    return fig, ax


def generate_markdown_table(gamma, mu, rho, zeta, lambda_p):
    # Start the table with the header
    table = r"| | $\gamma$ | $\mu$ | $\rho$ | $\zeta$ | $\lambda_i$ |"
    table += "\n|--|-------|----|-----|------|----------|\n"

    # Add the rows
    i = 0
    for g, m, r, z, l in zip(gamma, mu, rho, zeta, lambda_p):
        table += f"| Run {i}| {g} | {m} | {r} | {z} | {l} |\n"
        i += 1

    return table


def dict_to_table(d):
    # Create the header row
    headers = "| " + " | ".join(d.keys()) + " |\n"
    separators = "| " + " | ".join(["---"] * len(d)) + " |\n"

    # Create rows for each item in the lists
    rows = ""
    max_len = max(len(lst) for lst in d.values())
    for i in range(max_len):
        row = (
            "| "
            + " | ".join(str(d[key][i]) if i < len(d[key]) else "" for key in d.keys())
            + " |\n"
        )
        rows += row

    # Combine the header, separators, and all rows
    table = headers + separators + rows
    return table
