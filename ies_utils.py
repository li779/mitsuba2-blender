import numpy as np
from skimage.io import imsave
# import matplotlib.pyplot as plt

def parse_data_from_line(f_handle, num_val_to_read):
	num_phis_read = 0
	# read_new_line = True
	vert_angles = []
	while(num_phis_read < num_val_to_read):
		
		line = f_handle.readline()
		strings = line.split()

		for num in strings:
			vert_angles.append(float(num))
			num_phis_read += 1

	return vert_angles

def read_ies_data(fn):
	with open(fn, 'r') as f:
		# ignore first 10 lines
		for _ in range(10):
			line = f.readline()

		# get number of vert angles
		line = f.readline()
		num_phis = int(line)
		# get number of hori angles
		line = f.readline()
		num_thetas = int(line)

		# ignore next 4 lines
		for _ in range(4):
			f.readline()

		# ignore the actual phi and theta vals
		parse_data_from_line(f, num_phis)
		parse_data_from_line(f, num_thetas)

		ies_data = np.zeros((num_phis, num_thetas), np.float32)

		# each line contains data for a single hori angle
		for i in range(num_thetas):
			ies_data[:,i] = np.array(parse_data_from_line(f, num_phis))

	return ies_data


def convert_ies_to_image(fn, outfn):
	ies_data = read_ies_data(fn)
	# plt.imshow(ies_data)
	# plt.show()
	imsave(outfn, ies_data)

if __name__ == '__main__':
	fn = "/home/arpit/Downloads/check_ies_export/rayfile_LT_T66G_20190621_IES.ies"
	convert_ies_to_image(fn, "/home/arpit/Downloads/check_ies_export/ies_lights.tiff")
