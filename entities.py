# Entities

import settings
import RNG
import heapq
import numpy as np
import csv
import random

class State:
    S, E, I, H, F, R = range(6)
           
class Country(object):
    def __init__(self, name, code, pop, s_e, e_i, i_h, i_f, i_r, h_f, h_r, f_r, I0):
        self.name = name
        self.code = code
        self.pop = int(pop)
        
        # State Transition Rates
        self.s_e = float(s_e)
        self.e_i = float(e_i)
        self.i_h = float(i_h)
        self.i_f = float(i_f)
        self.i_r = float(i_r)
        self.h_f = float(h_f)
        self.h_r = float(h_r)
        self.f_r = float(f_r)

        # Containers for compartmentalized model of population
        self.S = self.pop
        self.E = []
        self.I = []
        self.H = []
        self.F = []
        self.R = []
        
        # Seed initial infected (I) population
        if I0 > 0:
            self.S = self.S - I0
            self.I = [Person(location = self, state = State.I) for p in range(I0)]
            
    def Update_Disease_Model(self):
        """Recalculate state transition parameters based on current population makeup
        
        No return value
        """
        raise NotImplementedError
        
    def Travel_Reduction(self):
        if len(self.I) > settings.THRESHOLD:
            reduction_factor = settings.REDUCTION_0 + settings.REDUCTION_SLOPE * (len(self.I) - settings.THRESHOLD)
            return reduction_factor
        else:
            return None

   def Disease_Transition(self):
        transition_rates_dict=dict(zip(['SE','EI','IH','IF','IR','HF','HR','FR'][self.s_e,self.e_i,self.i_h,self.i_f,self.i_r,self.h_f,self.h_r,self.f_r])
        keys=sorted(transition_rates_dict, key=transition_rates_dict.get)
        values=sorted(transition_rates_dict.values())
        temp=np.cumsum(values)
        index=np.argmax(temp,random.randrange(temp[0],temp[len(temp)-1]))
        if(keys[index]=='SE'):
            self.S=self.S-1
            self.E.append(Person(self.code)) #create person object
        elif(keys[index]=='EI'):
            person_trans=self.E.pop
            person_trans.state='I'
            self.I.append(person_trans) 
        elif(keys[index]=='IH'):
            person_trans=self.I.pop
            person_trans.state='H'
            self.H.append(person_trans)
        elif(keys[index]=='IF'):
            person_trans=self.I.pop
            person_trans.state='F'
            self.F.append(person_trans)
        elif(keys[index]=='IR'):
            person_trans=self.I.pop
            person_trans.state='R'
            self.R.append(person_trans)
        elif(keys[index]=='HF'):
            person_trans=self.H.pop
            person_trans.state='F'
            self.F.append(person_trans)
        elif(keys[index]=='HR'):
            person_trans=self.H.pop
            person_trans.state='R'
            self.R.append(person_trans)
        elif(keys[index]=='FR'):
            person_trans=self.F.pop
            person_trans.state='R'
            self.R.append(person_trans)

        
class Person(object):
    def __init__(self, location, state = State.E):
        """Instantiate a Person object when there is a transition from S->E (default)
        
        Keyword arguments:
        location -- a country object indicating the country this person occupies
        state    -- a State object corresponding to one of {S,E,I,F,H,R} indicating
                    the disease state of the individual
                    
        In general, only individuals in states other than S will be instantiated,
        lest the memory get out of control.
        """
        self.location = location
        self.state = state
        
class Flight_Generator(object):
    flightq = []
    routes = []
    
    @classmethod
    def Initialize(cls, countries):
        cls.flightq = []
        cls.routes = []
        with open('relevant_routes.csv') as csvfile:
            csvreader = csv.reader(csvfile,delimiter=',')
            csvreader.next()
            for row in csvreader:
                orig = [c for c in countries if c.name == row[-5]][0]
                dest = [c for c in countries if c.name == row[-4]][0]
                T = float(row[-3])
                T_std = float(row[-2])
                seats = int(row[-1])
                cls.routes.append(Route(orig,dest,T,T_std,seats))
                cls.routes[-1].Schedule_Next(0)                

    @classmethod
    def Schedule_Flight(cls, time, route):
        heapq.heappush(cls.flightq, (time, route))

    @classmethod
    def Reduce(cls, country, factor):
        affected_routes = [r for r in cls.routes if r.orig == country or r.dest == country]
        for r in affected_routes:
            r.T = factor*r.T
    
    @classmethod
    def Execute_Todays_Flights(cls, Now):
        while(cls.flightq[0][0] == Now):
            _, flight = heapq.heappop(cls.flightq)
            
            #select individuals at random from the S & E populations
            poisson_lambda=float(len(flight.orig.E))/float(len(flight.orig.E)+flight.orig.S)
            s=np.sum(RNG.Poisson(poisson_lambda, flight.seats))

            #remove them from origin population list and add to destination population list
            if s > 0:
                s = len(flight.orig.E) if s > len(flight.orig.E) else s
                np.random.shuffle(flight.orig.E)
                exposed_transfer=flight.orig.E[:s]
                flight.orig.E = flight.orig.E[s:]
            
                # TODO : make the selection from I population random such as:
                #         infected_transfer = [flight.orig.I[i] for i in sorted(np.random.sample(xrange(len(flight.orig.I)),s))]
            
                flight.dest.E.extend(exposed_transfer)
     
                #update these individuals' location with the destination
                for individual in exposed_transfer:
                    individual.location = flight.dest
     
            flight.orig.S=flight.orig.S - (flight.seats - s)
            flight.dest.S=flight.orig.S + (flight.seats - s)
            flight.orig.pop = flight.orig.pop - flight.seats
            flight.dest.pop = flight.dest.pop + flight.seats
            
            #schedule next flight
            flight.Schedule_Next(Now)
        
class Route(object):
    def __init__(self, orig, dest, mean_period, std_period, seats):
        self.orig = orig
        self.dest = dest
        self.T = mean_period
        self.T_std = std_period
        self.seats = seats
    
    def Schedule_Next(self,Now):
        delta_t = abs(int(RNG.Normal(self.T, self.T_std)))
        Flight_Generator.Schedule_Flight(Now+delta_t, self)
