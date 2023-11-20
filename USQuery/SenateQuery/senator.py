class senator(object):
    def __init__(self, name, party, state, img_link, recent_votes):
        self.name = name
        self.party = party
        self.state = state
        self.img_link = img_link
        self.recent_votes = recent_votes
    
    def getName(self):
        return self.name
    
    def getParty(self):
        return self.party
    
    def getState(self):
        return self.state
    
    def getImg(self):
        return self.img_link
    
    def getRVotes(self):
        return self.recent_votes
    
        


