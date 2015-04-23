from __future__ import division
import numpy as np
from scipy.special import erf
from scipy.optimize import minimize

from VISolver.Domain import Domain


class CloudServices(Domain):

    def __init__(self,Network,alpha=2):
        # raise NotImplementedError('Under construction.')
        self.UnpackNetwork(*Network)
        self.Network = (Network[0],Network[1])
        self.Dim = self.CalculateNetworkSize()
        self.alpha = alpha

    def F(self,Data):
        return -self.dCloudProfits(Data)

    def gap_rplus(self,Data):
        X = Data
        dFdX = self.F(Data)

        Y = np.maximum(0,X - dFdX/self.alpha)
        Z = X - Y

        return np.dot(dFdX,Z) - self.alpha/2.*np.dot(Z,Z)

    # Functions used to Initialize the Cloud Network and Calculate F

    def UnpackNetwork(self,nClouds,nBiz,c_clouds,c_bizes,dist_bizes,
                      lam_bizes,p_bizes):
        self.nClouds = nClouds
        self.nBiz = nBiz
        self.c_clouds = c_clouds
        self.c_bizes = c_bizes
        self.dist_bizes = dist_bizes
        self.lam_bizes = lam_bizes
        self.p_bizes = p_bizes
        self.q = np.zeros((self.nBiz,2*self.nClouds))

    def CalculateNetworkSize(self):
        return 2*self.nClouds*(self.nBiz + 1)

    def CloudProfits(self,Data):
        half = len(Data)//2

        p_L = Data[:half]
        p_S = Data[half:]

        q = np.zeros_like(self.q)
        for j in xrange(self.nBiz):
            q[j] = self.argmax_firm_profit(Data,j)
        self.q = q

        Q_L = np.sum(q[:,:half],axis=0)
        Q_S = np.sum(q[:,half:],axis=0)
        Q = Q_L + Q_S

        Revenue = p_L*Q_L + p_S*Q_S

        Cost = np.zeros(self.nClouds)
        for i in xrange(self.nClouds):
            Cost[i] = self.exp2lin(Q[i],*self.c_clouds[i])
        return Revenue - Cost

    def CloudProfit(self,Data,i):
        p_L = Data[i]
        p_S = Data[i+self.nClouds]

        q = np.zeros_like(self.q)
        for j in xrange(self.nBiz):
            q[j] = self.argmax_firm_profit(Data,j)
        self.q = q

        Q_L = np.sum(q[:,i])
        Q_S = np.sum(q[:,i+self.nClouds])
        Q = Q_L + Q_S

        Revenue = p_L*Q_L + p_S*Q_S

        Cost = self.exp2lin(Q,*self.c_clouds[i])

        return Revenue - Cost

    def dCloudProfits(self,Data):
        delta = 1e-5
        findiff = np.zeros_like(Data)
        pert = np.zeros_like(Data)
        pert[-1] = delta
        for i in xrange(Data.shape[0]):
            pert = np.roll(pert,1)
            f = lambda x: self.CloudProfit(x,i)
            findiff[i] = self.forwdiff(f,Data,Data+pert,delta)

    def nngauss_pdf(self,x,mu,sigma):
        if x >= 0.:
            N = 2./(1.-erf(-mu/(sigma*np.sqrt(2.)))) * \
                1./(sigma*np.sqrt(2.*np.pi))
            gauss = np.exp(-(x-mu)**2./(2.*sigma**2.))
            return N*gauss
        else:
            return 0.

    def nngauss_cdf(self,x,mu,sigma):
        if x >= 0.:
            a = erf()
            b = erf(-mu/(sigma*np.sqrt(2.)))
            return 1./2.*(a-b)
        else:
            return 0.

    def nngauss_intcdf(self,x,mu,sigma):
        if x >= 0.:
            xi = -mu/(sigma*np.sqrt(2.))
            eta = xi*erf(xi)
            kappa = 1./np.sqrt(np.pi)*np.exp(-xi**2.)
            _x = (x-mu)/(sigma*np.sqrt(2.))
            return 1./2.*(_x*erf(_x) +
                          1./np.sqrt(np.pi)*np.exp(-_x**2.) -
                          eta - kappa - eta/xi*x)

    def nngauss_mean(self,mu,sigma):
        skew = 2./(1.-erf(-mu/(sigma*np.sqrt(2.)))) * sigma/np.sqrt(2.*np.pi)
        return mu + skew

    def exp2lin(self,x,a,b,c):
        if x <= 0.:
            return 0.
        elif x <= b:
            return 1./c*(np.exp(x/a)-1.)
        else:
            return 1./c*(np.exp(b/a)*(x/a+1-b/a)-1)

    def dexp2lin(self,x,a,b,c):
        if x <= 0.:
            return 0.
        elif x <= b:
            return 1./(a*c)*np.exp(x/a)
        else:
            return 1./(a*c)*np.exp(b/a)

    def firm_profit(self,q,dp,lam,mu,intcdf):
        half = len(q)//2
        Ql = np.sum(q[:half])
        return np.sum(q*dp) + lam[1]*(Ql-mu) - (lam[0]+lam[1])*intcdf(Ql)

    def dfirm_profit(self,q,dp,lam,cdf):
        half = len(q)//2
        Ql = np.sum(q[:half])
        res = np.empty_like(dp)
        res[:half] = dp[:half] + lam[1] - (lam[0]+lam[1])*cdf(Ql)
        res[half:] = dp[half:]
        return res

    def forwdiff(self,f,x,_x,h):
        return (f(_x)-f(x))/h

    def argmax_firm_profit(self,Data,j):
        x0 = self.q[j]
        mu, sigma = self.dist_bizes[j]
        lam = self.lam_bizes[j]
        dp = self.p_bizes[j] - Data

        intcdf = lambda x: self.nngauss_intcdf(x,mu,sigma)
        fun = lambda q: -self.firm_profit(q,dp,lam,mu,intcdf)

        cdf = lambda x: self.nngauss_cdf(x,mu,sigma)
        dfun = lambda q: -self.dfirm_profit(q,dp,lam,cdf)

        bnds = tuple([(0,None)]*len(x0))

        res = minimize(fun,x0,jac=dfun,method='SLSQP',bounds=bnds)

        return res.x


def CreateRandomNetwork(nClouds=3,nBiz=10,seed=None):

    if seed is not None:
        np.random.seed(seed)

    # Cloud cost function parameters
    # a: small --> large means large --> small linear slope
    # b: transition point from exp to lin
    # c: scaling factor for costs
    # c_clouds = 0*(np.random.rand(nClouds,3)*[0,.5,.2]+[1,1,1])
    c_clouds = np.array([[21.,23.,1.],
                         [27.,43.,1.],
                         [32.,68.,1.]])

    # Business cost functions
    # Unused for now
    # c_bizes = np.random.rand(nBiz,3)*[0,0.2,0.1]+[0,0,0]
    c_bizes = np.zeros((nBiz,3))

    # Business demand distribution function means, mu_biz, and
    # standard deviations, sigma_biz
    # dist_bizes = np.random.rand(nBiz,2)*[0.2,0.02]+[2,.8]
    dist_bizes = np.array([[10.,2.],
                           [15.,3.],
                           [18.,5.],
                           [20.,4.],
                           [23.,7.],
                           [26.,6.],
                           [30.,4.],
                           [13.,5.],
                           [17.,2.],
                           [24.,5.]])
    # mu = dist_bizes[:,0]
    # sigma = dist_bizes[:,1]
    # means = np.exp(mu+0.5*sigma**2)
    # variances = (np.exp(sigma**2)-1)*(means**2)

    # Business forecasting cost functions
    # = lam_biz[0]*E_surplus + lam_biz[1]*E_shortage
    # lam_bizes = np.random.rand(nBiz,2)*[0,0.01]+[0,0.005]
    lam_bizes = np.array([[.1,.1],
                          [.1,.1],
                          [.1,.1],
                          [.1,.1],
                          [.1,.1],
                          [.1,.1],
                          [.1,.1],
                          [.1,.1],
                          [.1,.1],
                          [.1,.1]])

    # Business sale prices, p_biz
    # p_bizes = np.random.rand(nBiz)*1+5
    p_bizes = np.array([.3,.4,.2,.5,.6,.4,.3,.2,.5,.3])

    return (nClouds,nBiz,c_clouds,c_bizes,dist_bizes,lam_bizes,p_bizes)