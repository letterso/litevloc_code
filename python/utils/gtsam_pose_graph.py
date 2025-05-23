import numpy as np
import gtsam

class PoseGraph:
	def __init__(self):
		"""Initialize gtsam factor graph and isam"""
		self.graph = gtsam.NonlinearFactorGraph()
		self.initial_estimate = gtsam.Values()
		self.current_estimate = gtsam.Values()
		
		self.isam = gtsam.ISAM2()
		self.params = gtsam.ISAM2Params()

	def add_prior_factor(self, key: int, pose: gtsam.Pose3, sigma: np.ndarray):
		noise_model = gtsam.noiseModel.Diagonal.Sigmas(sigma)
		self.graph.add(gtsam.PriorFactorPose3(key, pose, noise_model))

	def add_odometry_factor(self, 
							prev_key: int, prev_pose: gtsam.Pose3, 
							curr_key: int, curr_pose: gtsam.Pose3, 
							sigma: np.ndarray):
		noise_model = gtsam.noiseModel.Diagonal.Sigmas(sigma)		
		delta_pose = prev_pose.between(curr_pose)
		self.graph.add(gtsam.BetweenFactorPose3(prev_key, curr_key, delta_pose, noise_model))

	def add_init_estimate(self, key: int, pose: gtsam.Pose3):
		if self.initial_estimate.exists(key):
			self.initial_estimate.erase(key)
			self.initial_estimate.insert(key, pose)
		else:
			self.initial_estimate.insert(key, pose)

	def perform_optimization(self):
		self.isam.update(self.graph, self.initial_estimate)
		self.current_estimate = self.isam.calculateEstimate()
		self.graph.resize(0)
		self.initial_estimate.clear()
		result = {'current_estimate': self.current_estimate}

		return result
	def get_margin_covariance(self, key: int):
		if self.current_estimate.exists(key):
			return self.isam.marginalCovariance(key)
		else:
			return None

	def get_factor_graph(self):
		return self.graph

	def get_initial_estimate(self):
		return self.initial_estimate

	def get_current_estimate(self):
		return self.current_estimate

	@staticmethod
	def add_robust_kernel(graph):
		graph_robust = gtsam.NonlinearFactorGraph()
		##### Huber robust kernel
		# robust_model = gtsam.noiseModel.mEstimator.Huber.Create(k=1.345)
		##### Cauchy robust kernel
		robust_model = gtsam.noiseModel.mEstimator.Cauchy.Create(k=0.3)
		#####
		for key in range(graph.size()):
			factor = graph.at(key)
			# TODO(gogojjh): Add robust kernel to othre factors
			if isinstance(factor, gtsam.BetweenFactorPose3):
				key1, key2 = factor.keys()
				noise_model = gtsam.noiseModel.Robust.Create(
					robust_model, factor.noiseModel()
				)
				new_factor = gtsam.BetweenFactorPose3(key1, key2, factor.measured(), noise_model)
				graph_robust.add(new_factor)
			else:
				graph_robust.add(factor.clone())
		
		return graph_robust

	@staticmethod
	def find_connected_components(graph):
		"""
		Find disconnected subgraphs using basic data structures.
		Return:
			components: [component1, component2, ...]
				component1: [key1, key2, ...] without sorting key id
		"""		
		# Build adjacency list using regular dict
		adjacency = {}
		all_keys = set()
		for key in range(graph.size()):
			factor = graph.at(key)
			if isinstance(factor, gtsam.BetweenFactorPose3):
				key1, key2 = factor.keys()
				if key1 not in adjacency:
					adjacency[key1] = set()
				if key2 not in adjacency:
					adjacency[key2] = set()
				adjacency[key1].add(key2)
				adjacency[key2].add(key1)
				
				all_keys.add(key1)
				all_keys.add(key2)

		visited = set()
		components = []
		# BFS implementation using list-as-queue
		for key in all_keys:
			if key not in visited:
				queue = [key]
				visited.add(key)
				component = []
				while queue:
					current = queue.pop()  # Dequeue from front
					component.append(current)
					if current in adjacency:
						for neighbor in adjacency[current]:
							if neighbor not in visited:
								visited.add(neighbor)
								queue.append(neighbor)
				
				components.append(component)

		return components
	@staticmethod
	def optimize_pose_graph_with_LM(graph, initial, verbose=False, robust_kernel=False):
		"""
		Optimizes a pose graph using the Levenberg-Marquardt algorithm.

		This function adds a prior factor to the first key in the initial estimate to anchor the graph,
		then optimizes the graph to minimize the error.

		Args:
			graph (gtsam.NonlinearFactorGraph): The pose graph containing factors (constraints).
			initial (gtsam.Values): Initial estimates for the variables (poses) in the graph.
			verbose (bool): Whether to print optimization progress.
			robust_kernel (bool): Whether to use a robust kernel for the optimization.

		Returns:
			gtsam.Values: The optimized values (poses) after the optimization process.
		"""    
		# Set up the optimizer
		params = gtsam.LevenbergMarquardtParams()
		if verbose:
			params.setVerbosity("Termination")
		
		if robust_kernel:
			graph_robust = PoseGraph.add_robust_kernel(graph)
			optimizer = gtsam.LevenbergMarquardtOptimizer(graph_robust, initial, params)
		else:
			optimizer = gtsam.LevenbergMarquardtOptimizer(graph, initial, params)
		
		result = optimizer.optimize()
		
		return result	

	@staticmethod
	def plot_pose_graph(save_dir, graph, results, titles, mode='2d', subgraph_keys=None):
		import os
		from matplotlib import pyplot as plt

		fig, axes = plt.subplots(1, len(results), subplot_kw={'projection': '3d'})		
		for ax, title, result in zip(axes, titles, results):
			resultPoses = gtsam.utilities.allPose3s(result)
			print(f"Number of resultPoses: {resultPoses.size()}")
			x_coords = [resultPoses.atPose3(i).translation()[0] for i in range(resultPoses.size())]
			y_coords = [resultPoses.atPose3(i).translation()[1] for i in range(resultPoses.size())]
			z_coords = [resultPoses.atPose3(i).translation()[2] for i in range(resultPoses.size())]
			ax.plot(x_coords, y_coords, z_coords, 'o', color='b', label='Est. Trajectory', markersize=3)

			for key in range(graph.size()):
				factor = graph.at(key)
				if isinstance(factor, gtsam.BetweenFactorPose3):
					key1, key2 = factor.keys()
					tsl1 = result.atPose3(key1).translation()
					tsl2 = result.atPose3(key2).translation()
					ax.plot([tsl1[0], tsl2[0]], [tsl1[1], tsl2[1]], [tsl1[2], tsl2[2]], '-', color='g', lw=1)

			if subgraph_keys is not None:
				for graph_id, keys in enumerate(subgraph_keys):
					tsl = result.atPose3(keys[0]).translation()
					ax.text(tsl[0], tsl[1], tsl[2], f'{graph_id}', fontsize=12, color='r', ha='center')

			ax.set_xlabel('X [m]')
			ax.set_ylabel('Y [m]')
			ax.set_zlabel('Z [m]')
			ax.set_title(title)
			if mode == '2d':
				ax.view_init(elev=90, azim=90)
			elif mode == '3d':
				ax.view_init(elev=55, azim=60)
			ax.axis('equal')

		plt.tight_layout()
		if save_dir:
			plt.savefig(os.path.join(save_dir, 'pose_graph_refined.png'))
		else:
			plt.show()
