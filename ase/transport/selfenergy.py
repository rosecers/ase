import numpy as npy
from ase.transport.tools import dagger


class LeadSelfEnergy:
    conv = 1e-8 # Convergence criteria for surface Green function
    
    def __init__(self, hs_dii, hs_dij, hs_dim, eta=1e-4):
        self.h_ii, self.s_ii = hs_dii # onsite principal layer
        self.h_ij, self.s_ij = hs_dij # coupling between principal layers
        self.h_im, self.s_im = hs_dim # coupling to the central region
        self.nbf = self.h_im.shape[1] # nbf for the scattering region
        self.eta = eta
        self.energy = None
        self.bias = 0
        self.sigma_mm = npy.empty((self.nbf, self.nbf), complex)

    def __call__(self, energy):
        """Return self-energy (sigma)"""
        if energy != self.energy:
            self.energy = energy
            z = energy - self.bias + self.eta * 1.j           
            tau_im = z * self.s_im - self.h_im
            a_im = npy.linalg.solve(self.get_sgfinv(energy), tau_im)
            tau_mi = z * dagger(self.s_im) - dagger(self.h_im)
            self.sigma_mm[:] = npy.dot(tau_mi, a_im)

        return self.sigma_mm

    def set_bias(self, bias):
        self.bias = bias

    def get_lambda(self, energy):
        """Return the lambda (aka Gamma) defined by i(S-S^d).

        Here S is the retarded selfenergy, and d denotes the hermitian
        conjugate.
        """
        sigma_mm = self(energy)
        return 1.j * (sigma_mm - dagger(sigma_mm))
        
    def get_sgfinv(self, energy):
        """The inverse of the retarded surface Green function""" 
        z = energy - self.bias + self.eta * 1.0j
        
        v_00 = z * dagger(self.s_ii) - dagger(self.h_ii)
        v_11 = v_00.copy()
        v_10 = z * self.s_ij - self.h_ij
        v_01 = z * dagger(self.s_ij) - dagger(self.h_ij)

        delta = self.conv + 1
        n = 0
        while delta > self.conv:
            a = npy.linalg.solve(v_11, v_01)
            b = npy.linalg.solve(v_11, v_10)
            v_01_dot_b = npy.dot(v_01, b)
            v_00 -= v_01_dot_b
            v_11 -= npy.dot(v_10, a) 
            v_11 -= v_01_dot_b
            v_01 = -npy.dot(v_01, a)
            v_10 = -npy.dot(v_10, b)
        
            delta = npy.abs(v_01).max()
            n += 1

        return v_00


def hartree(D, V_ijkl):
    if type(D) == list:
        D = D[0] + D[1]
    else:
        D = 2 * D

    N = len(D)
    V_H = npy.empty([N, N], complex)
    for i in range(N):
        for j in range(N):
            V_H[i, j] = npy.dot(V_ijkl[i, :, j, :].ravel(), D.flat)
    return V_H


def hartree_partial(D, V_ijij, V_ijji, V_iijj, V_iiij, V_ikjk=None):
    if type(D) == list:
        D = D[0] + D[1]
    else:
        D = 2 * D

    N = len(D)
    V_H = npy.empty([N, N], complex)
    if V_iijj is None:
        V_iijj = npy.zeros([N, N], complex)
    if V_iiij is None:
        V_iiij = npy.zeros([N, N], complex)
    for i in range(N):
        for j in range(N):
            if i == j:
                if V_ikjk is not None:
                    V_H[i, i] = npy.sum(D * V_ikjk[:, :, i])
                else:
                    V_H[i, i] = (npy.dot(D.diagonal(), V_ijij[i]) +
                                 npy.dot(D[i], V_iiij[i]) +
                                 npy.dot(D[:, i], V_iiij[i].conj()) -
                                 2 * D[i, i] * V_iiij[i, i])
            else:
                V_H[i, j] = (D[i, j] * V_iijj[i, j] +
                             D[j, i] * V_ijji[i, j] +
                             D[i, i] * V_iiij[i, j] +
                             D[j, j] * V_iiij[j, i].conj())
                if V_ikjk is not None:
                    V_H[i, j] += (npy.dot(D.diagonal(), V_ikjk[i, j, :]) -
                                  D[i, i] * V_iiij[i, j] -
                                  D[j, j] * V_iiij[j, i].conj())
    return V_H


def fock(D, V_ijkl):
    if type(D) == list:
        return [fock(D[0], V_ijkl), fock(D[1], V_ijkl)]

    N = len(D)
    V_F = npy.empty([N, N], complex)
    for i in range(N):
        for j in range(N):
            V_F[i, j] = -npy.dot(V_ijkl[i, :, :, j].ravel(), D.flat)
    return V_F


def fock_partial(D, V_ijij, V_ijji, V_iijj, V_iiij, V_ikjk=None):
    if type(D) == list:
        return [GetFockAll(D[0], V_ijkl), GetFockAll(D[1], V_ijkl)]
    
    N = len(D)
    V_F = npy.empty([N, N], complex)
    if V_iijj is None:
        V_iijj = npy.zeros([N, N], complex)
    if V_iiij is None:
        V_iiij = npy.zeros([N, N], complex)
    for i in range(N):
        for j in range(N):
            if i == j:
                V_F[i, i] = -(npy.dot(D.diagonal(), V_ijji[i]) +
                              npy.dot(D[i], V_iiij[i]) +
                              npy.dot(D[:, i], V_iiij[i].conj()) -
                              2 * D[i, i] * V_iiij[i, i] +
                              D[i, i] * V_ijij[i, i] - D[i, i] * V_ijji[i, i])
            else:
                V_F[i, j] = -(D[j, i] * V_ijij[i, j] +
                              D[i, j] * V_iijj[i, j] +
                              D[i, i] * V_iiij[i, j] +
                              D[j, j] * V_iiij[j, i].conj())
                if V_ikjk is not None:
                    V_F[i, j] -= (
                        npy.dot(D[:, i], V_ikjk[:, j, i]) -
                        D[i, i] * V_ikjk[i, j, i] - D[j, i] * V_ikjk[j, j, i] +
                        npy.dot(D[j, :], V_ikjk[i, :, j]) -
                        D[j, j] * V_ikjk[i, j, j] - D[j, i] * V_ikjk[i, i, j])
    return V_F
