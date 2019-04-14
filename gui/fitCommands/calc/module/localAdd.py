import wx
from logbook import Logger

import eos.db
from eos.exception import HandledListActionError
from gui.fitCommands.helpers import stateLimit
from service.fit import Fit


pyfalog = Logger(__name__)


class CalcAddLocalModuleCommand(wx.Command):

    def __init__(self, fitID, newModInfo):
        wx.Command.__init__(self, True, 'Add Module')
        self.fitID = fitID
        self.newModInfo = newModInfo
        self.savedPosition = None
        self.subsystemCmd = None

    def Do(self):
        pyfalog.debug('Doing addition of local module {} to fit {}'.format(self.newModInfo, self.fitID))
        sFit = Fit.getInstance()
        fit = sFit.getFit(self.fitID)

        newMod = self.newModInfo.toModule(fallbackState=stateLimit(self.newModInfo.itemID))
        if newMod is None:
            return False

        # If subsystem and we need to replace, run the replace command instead and bypass the rest of this command
        if newMod.item.category.name == 'Subsystem':
            for oldMod in fit.modules:
                if oldMod.getModifiedItemAttr('subSystemSlot') == newMod.getModifiedItemAttr('subSystemSlot') and newMod.slot == oldMod.slot:
                    from .localReplace import CalcReplaceLocalModuleCommand
                    self.subsystemCmd = CalcReplaceLocalModuleCommand(fitID=self.fitID, position=oldMod.modPosition, newModInfo=self.newModInfo)
                    return self.subsystemCmd.Do()

        if not newMod.fits(fit):
            pyfalog.warning('Module does not fit')
            return False

        newMod.owner = fit
        try:
            fit.modules.append(newMod)
        except HandledListActionError:
            pyfalog.warning('Failed to append to list')
            eos.db.commit()
            return False
        sFit.checkStates(fit, newMod)
        eos.db.commit()
        self.savedPosition = newMod.modPosition
        return True

    def Undo(self):
        pyfalog.debug('Undoing addition of local module {} to fit {}'.format(self.newModInfo, self.fitID))
        # We added a subsystem module, which actually ran the replace command. Run the undo for that guy instead
        if self.subsystemCmd is not None:
            return self.subsystemCmd.Undo()
        from .localRemove import CalcRemoveLocalModuleCommand
        if self.savedPosition is None:
            return False
        cmd = CalcRemoveLocalModuleCommand(fitID=self.fitID, positions=[self.savedPosition])
        return cmd.Do()
