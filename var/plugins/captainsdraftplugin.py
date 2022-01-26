# Captains Draft Plugin
# This plugin provides a mode to pick teams whereby assigned captains take turns drafting players

# Author: Jazcash

# Usage: !preset draft
# AllyTeam 3 represents the list of 'added' players. When the draft preset is enabled, all current players get added and moved to AllyTeam 3
# Players can 'unadd' at any time by simply becoming a spectator
# !draft must be called to begin the drafting phase. An even number of players is required to begin drafting with at least 6 players minimum
# The two highest TS players are then automatically made captains of each team
# The lowest TS of the two captains gets first pick. Players are picked with !pick [username]
# Players are picked one after another, until all players are picked
# Players must !cv start as normal
# Once game has finished, plugin reverts to adding state

import perl
import sys
import traceback
from collections import Counter
from datetime import datetime

spads=perl.CaptainsDraftPlugin
pluginVersion='0.4'
requiredSpadsVersion='0.12.29'
globalPluginParams = {
    'commandsFile': ['notNull'],
    'helpFile': ['notNull']
}
presetPluginParams = None

accountIdSkill = {}
playerNameSkill = {}

def getVersion(pluginObject):
    return pluginVersion

def getRequiredSpadsVersion(pluginName):
    return requiredSpadsVersion

def getParams(pluginName):
    return [globalPluginParams, presetPluginParams]

class CaptainsDraftPlugin:
    def __init__(self, context):
        try:
            lobbyInterface = spads.getLobbyInterface()
            spads.addSpadsCommandHandler({
                'draft': self.draft,
                'pick': self.pick
            })

            if (spads.getLobbyState() > 3):
                self.onLobbyConnected(lobbyInterface)

            spads.slog("Plugin loaded (version %s)" % pluginVersion, 3)
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def onLobbyConnected(self, _lobbyInterface):
        try:
            spads.addLobbyCommandHandler({"CLIENTBATTLESTATUS": self.clientBattleStatusChange})
            self.reset()
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def onUnload(self, reason):
        try:
            spads.removeLobbyCommandHandler(['CLIENTBATTLESTATUS'])
            spads.removeSpadsCommandHandler(["draft", "pick"])

            spads.slog("Plugin unloaded", 3)
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def reset(self):
        try:
            self.state = "disabled" # disabled, adding, drafting, ready
            self.addedPlayers = set()
            self.playerPool = set()
            self.teamApicking = False
            self.teamAcap = ""
            self.teamBcap = ""
            self.teamA = set()
            self.teamB = set()
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def onBattleClosed(self):
        try:
            self.reset()
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def onBattleOpened(self):
        try:
            currentSpadsConf = spads.getSpadsConf()
            if (currentSpadsConf['preset'] == "draft"):
                self.state = "adding"
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def onSpringStop(self, _pid):
        try:
            if (self.state != "disabled"):
                spads.sayBattle(f"Game ended, returning to adding state")
                self.resetToAddingState()
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def onPresetApplied(self, oldPresetName, newPresetName):
        try:
            if (newPresetName == "draft"):
                self.disable()
                self.enable()
            else:
                self.disable()
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def onLeftBattle(self, userName):
        try:
            if (userName not in self.addedPlayers):
                return

            self.addedPlayers.discard(userName)

            if self.state == "drafting" or self.state == "ready":
                spads.sayBattle(f"{userName} left, returning to adding state")
                self.resetToAddingState()
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def enable(self):
        try:
            self.state = "adding"
            spads.sayBattle('Captains Draft enabled, call !draft to begin picking')

            lobbyInterface = spads.getLobbyInterface()
            users = lobbyInterface.getBattle()["users"]
            for userName in users:
                userStatus = users[userName]["battleStatus"]
                if (userStatus is not None and userStatus["mode"] == "1"):
                    self.addedPlayers.add(userName)

            self.fixPlayerStatuses()
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def disable(self):
        try:
            self.reset()
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def resetToAddingState(self):
        try:
            self.state = "adding"
            self.teamA = set()
            self.teamB = set()
            self.teamAcap = ""
            self.teamBcap = ""
            self.addedPlayers = set()
            self.playerPool.clear()
            self.fixPlayerStatuses()
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def draft(self, source, user, params, checkOnly):
        try:
            if (self.state != "adding"):
                spads.answer(f"Cannot start draft while Captains Draft is in the {self.state} state")
                return 0

            if (len(self.addedPlayers) % 2 != 0):
                spads.sayBattle(f"Can't start draft without an even number of players ({len(self.addedPlayers)} added)")
                return 0

            if (len(self.addedPlayers) < 6):
                spads.sayBattle(f"Can't start draft with less than 6 added players ({len(self.addedPlayers)} added)")
                return 0

            if (checkOnly):
                return 1

            self.state = "drafting"
            self.playerPool = self.addedPlayers.copy()
            self.updateSkills()
            self.assignCaptainsBySkill()
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def pick(self, source, user, params, checkOnly):
        try:
            if (self.state != "drafting"):
                spads.answer(f"Cannot pick player while Captains Draft is in the {self.state} state")
                return 0

            if len(params) == 0:
                spads.sayBattle(f"You must pick a player, e.g. !pick bob")
                return 0

            lobbyInterface = spads.getLobbyInterface()
            usersInBattle = list(lobbyInterface.getBattle()['users'])
            matchingUsers = perl.cleverSearch(params[0], usersInBattle)

            if (len(matchingUsers) == 0):
                spads.sayBattle(f"Player {params[0]} not found")
                return 0

            pickedPlayer = matchingUsers[0]
            cap = self.teamAcap if self.teamApicking else self.teamBcap
            otherCap = self.teamAcap if not self.teamApicking else self.teamBcap

            if ((user != self.teamAcap and user != self.teamBcap) or (user == self.teamAcap and not self.teamApicking) or (user == self.teamBcap and self.teamApicking)):
                spads.sayBattle(f"Only {cap} can !pick now")
                return 0

            if ((pickedPlayer in self.teamA) or (pickedPlayer in self.teamB)):
                spads.sayBattle(f"{pickedPlayer} has already been picked")
                return 0

            if (pickedPlayer not in self.playerPool):
                spads.sayBattle(f"{pickedPlayer} is not added")
                return 0

            self.playerPool.discard(pickedPlayer)
            if self.teamApicking:
                self.teamA.add(pickedPlayer)
            else:
                self.teamB.add(pickedPlayer)

            self.teamApicking = not self.teamApicking

            if (len(self.playerPool) > 1):
                spads.sayBattle(f"{cap} picked {pickedPlayer}. It is {otherCap}'s turn to !pick")
            else:
                lastUnpickedPlayer = self.playerPool.pop()
                spads.sayBattle(f"{lastUnpickedPlayer} is last pick so goes to {otherCap}\'s team")
                if self.teamApicking:
                    self.teamA.add(lastUnpickedPlayer)
                else:
                    self.teamB.add(lastUnpickedPlayer)

                self.ready()

            self.fixPlayerStatuses()
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def updatePlayerSkill(self, playerSkill, accountId, modName, gameType):
        try:
            accountIdSkill[accountId] = float(playerSkill["skill"])
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def updateSkills(self):
        try:
            lobbyInterface = spads.getLobbyInterface()
            serverUsers = lobbyInterface.getUsers()
            for playerName in serverUsers:
                player = serverUsers[playerName]
                accountId = player["accountId"]
                if accountId in accountIdSkill:
                    playerNameSkill[playerName] = accountIdSkill[player["accountId"]]
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def assignCaptainsBySkill(self):
        try:
            playerPoolList = list(self.playerPool)
            playerPoolList.sort(key=lambda x: playerNameSkill[x], reverse=True)
            self.teamAcap = playerPoolList[0]
            self.teamBcap = playerPoolList[1]
            self.teamA.add(self.teamAcap)
            self.teamB.add(self.teamBcap)
            self.playerPool.discard(self.teamAcap)
            self.playerPool.discard(self.teamBcap)

            self.fixPlayerStatuses()

            spads.sayBattle(f"Captains are {self.teamAcap} and {self.teamBcap}, based on TrueSkill. {self.teamBcap} gets first !pick")
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def clientBattleStatusChange(self, command, userName, battleStatus, teamColor):
        try:
            self.fixPlayerStatus(userName)
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def fixPlayerStatuses(self):
        try:
            if (self.state == "disabled"):
                return

            lobbyInterface = spads.getLobbyInterface()
            users = lobbyInterface.getBattle()["users"];

            for idx, userName in enumerate(users, start=1):
                self.fixPlayerStatus(userName, idx)
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def fixPlayerStatus(self, userName, index=-1):
        try:
            if (self.state == "disabled"):
                return

            status = self.getUserBattleStatus(userName)

            if (self.state == "adding"):
                if (status["isSpec"] and status["isAdded"]):
                    self.addedPlayers.discard(userName)
                elif (not status["isSpec"]):
                    self.addedPlayers.add(userName)
                    if (status["allyTeamId"] != 2):
                        self.forceAllyTeam(userName, 2)
            elif (self.state == "drafting"):
                if (status["isSpec"] and status["isAdded"]):
                    spads.sayBattle(f"{userName} specced, returning to adding state")
                    self.resetToAddingState()
                elif (not status["isSpec"] and not status["isAdded"]):
                    spads.sayBattle(f"{userName}, you must wait for the next draft")
                    self.forceSpec(userName)
                elif (status["isAdded"] and status["isTeamA"] and status["allyTeamId"] != 0):
                    self.forceAllyTeam(userName, 0)
                elif (status["isAdded"] and status["isTeamB"] and status["allyTeamId"] != 1):
                    self.forceAllyTeam(userName, 1)
                elif (status["isAdded"] and (not status["isTeamA"]) and (not status["isTeamB"]) and status["allyTeamId"] != 2):
                    self.forceAllyTeam(userName, 2)

            if index >= 0:
                spads.queueLobbyCommand(["FORCETEAMNO", userName, index])
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def forceSpec(self, userName):
        try:
            spads.queueLobbyCommand(["FORCESPECTATORMODE", userName]);
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def forceAllyTeam(self, userName, allyTeamId):
        try:
            spads.queueLobbyCommand(["FORCEALLYNO", userName, allyTeamId]);
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)

    def ready(self):
        spads.sayBattle("All players picked!")

    def getUserBattleStatus(self, userName):
        try:
            lobbyInterface = spads.getLobbyInterface()
            battleStatus = lobbyInterface.getBattle()["users"][userName]["battleStatus"]
            return {
                "isAdded": userName in self.addedPlayers,
                "isTeamA": userName in self.teamA,
                "isTeamB": userName in self.teamB,
                "isSpec": battleStatus["mode"] == 0,
                "allyTeamId": battleStatus["team"]
            }
        except Exception as e:
            spads.slog("Unhandled exception: " + str(sys.exc_info()[0]) + "\n" + str(traceback.format_exc()), 0)
