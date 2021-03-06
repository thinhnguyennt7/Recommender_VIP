import datetime
import logStatement as lg
import sys


# Helper method to check the time has the least
def compare(time1, time2):
    if len(time1) < len(time2):
        return 1
    elif len(time1) > len(time2):
        return -1
    else:
        timeOne = time1.split(":")
        timeTwo = time2.split(":")
        if (int(timeOne[0]) < int(timeTwo[0])):
            return 1
        elif (int(timeOne[0]) > int(timeTwo[0])):
            return -1
        else:
            return 0


# Estimate the total amount task should split out for each hostname
def taskSplitByNodeRequested(userID: str, nodeRequested: int, recommenderQueue: str, ssh):
    hostname, nodes, minCPU, lines = '', '', 100.0, ''
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command('pace-check-queue ' + recommenderQueue)
    serverLines = 'Requester ID: ' + userID + '\n\n' + 'NUMBER OF TASK/NP REQUESTED: ' + '[' + str(nodeRequested) + ']' + '\n\n'
    lineStart = 0 ; foundServer = False

    # Get out the one has the least CPU and core number
    for line in iter(ssh_stdout.readline, ""):
        lines += line
        dataNode = line.split()

        # Copy the titles
        if (len(dataNode) >= 8 and dataNode[0] == 'Hostname' and dataNode[5] == 'Mem%'):
            serverLines += line

        if lineStart >= 10 and len(dataNode) >= 8 and dataNode[6] != 'No' and dataNode[2] not in ['Nodes', 'Memory', 'Cpu%']:
            # Calculate the number of remainding node of the hostname
            currentTask = dataNode[1]
            spaceNodeRemain = numberOfCoreLeft(currentTask)

            # If the current remain node larger then the number of node requested
            if spaceNodeRemain >= nodeRequested:
                serverLines += line
                foundServer = True

                # Calculate the one has the least cpu in use
                if float(dataNode[2]) < float(minCPU):
                    minCPU = float(dataNode[2])
                    hostname = dataNode[0]
                    nodes = currentTask
        lineStart += 1

    # Write new data to logs
    rawDataPath = 'HostServerDetail_Data/' + str(getCurrentDateTime())
    lg.writeDataToTxtFile(rawDataPath, lines)

    if (not foundServer):
        serverLines += '**Can not find any queue has the match number of node requested**'
    writeServerPath = 'hostName_Core_Requested/' + 'newRelease'
    lg.writeDataToTxtFile(writeServerPath, serverLines)

    return [hostname, nodes, str(minCPU)]


# Return the current date with time
def getCurrentDateTime():
    return datetime.datetime.now()


# Collect of the total of walltime of each queues
def collectWallTimeQueue(ssh, sampleQueues):

    walltime, username = dict(), ''
    pathName = "paceWallTime_Data/" + "Queue_walltime"

    # If we already executed the command
    if not lg.checkFileInPath(pathName):
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command('pace-whoami')
        lines = ''

        for line in iter(ssh_stdout.readline, ""):
            lines += line
            queue_Node = line.split()
            if (len(queue_Node) != 0):
                if queue_Node[0] == 'userName':
                    username = queue_Node[2]
                if queue_Node[0] in sampleQueues:
                    walltime[queue_Node[0]] = queue_Node[1]

        # Write new data to logs
        lg.writeDataToTxtFile(pathName, lines)
    else:
        # Read the previous data from txt file
        data = lg.readDataFromTxtFile(pathName)
        _, username = data[3].split("=")

        for i in range(len(data) - 4, len(data), 1):
            # Get out the current queue name
            currentQueue = data[i][5: 5 + 20].strip()
            if (currentQueue in sampleQueues):
                # Begin index of string manipulation
                begin = 5 + len(currentQueue) + 10
                currentWallTime = data[i][begin : begin + 20]
                walltime[currentQueue] = currentWallTime.strip()

    return [walltime, username.strip()]


# Helper method to return the number of core cpu has left in the hostname
def numberOfCoreLeft(taskNp):
    left, right = taskNp.split('/')
    return int(right) - int(left)


def compareTimeRange(oldTime, newTime, time_range) -> bool:
    # Generate the old time range to real data value
    oldTimeRange = datetime.datetime(oldTime[0], oldTime[1], oldTime[2], oldTime[3], oldTime[4], oldTime[5])

    if oldTimeRange < getCurrentDateTime():
        diff_Year = newTime[0] - oldTime[0]
        diff_Month = newTime[1] - oldTime[1]
        diff_Date = newTime[2] - newTime[2]

        if diff_Year or diff_Month or diff_Date:
            return False

        diff_Hour = newTime[3] - oldTime[3]
        diff_Min =  newTime[4] - oldTime[4]

        if diff_Hour > 0:
            return False
        else:
            if diff_Min <= time_range:
                return True
            else:
                return False
    return True


# Determine if the last executed fall under 10 mins
def justExecuted(time_range: int) -> bool:
    pathName = "lastExecution/recently"

    if not lg.checkFileInPath(pathName):
        return False
    else:
        # Last execution file
        previousExecutedDate = lg.readDataFromTxtFile("lastExecution/recently")[0]

        # Get the last execution time
        dateExecuted = previousExecutedDate[10:20]
        timeExecuted = previousExecutedDate[21:29]
        oldYear, oldMonth, oldDay = dateExecuted.split("-")
        oldHour, oldMinutes, oldSecond = timeExecuted.split(":")
        oldTime = [int(oldYear), int(oldMonth), int(oldDay), int(oldHour), int(oldMinutes), int(oldSecond)]

        # Get the current time
        currentTime = str(getCurrentDateTime())
        date = currentTime[0:10]
        time = currentTime[11:19]
        year, month, day = date.split("-")
        hour, minutes, second = time.split(":")
        newTime = [int(year), int(month), int(day), int(hour), int(minutes), int(second)]

        return compareTimeRange(oldTime, newTime, time_range)


# Verify if the recently file data has correct data or not
def verifyData(nodeRequested: int) -> bool:
    # The path address
    pathName, previousNumberOfNode, currentQueueInFile = "lastExecution/recently", [], ''
    queueAnalysisPath, hashDict = "Queue_Analysis/NewestFetch", {}

    if not lg.checkFileInPath(pathName) or not lg.checkFileInPath(queueAnalysisPath):
        return False
    else:
        # Last execution file
        rawData = lg.readDataFromTxtFile(pathName)
        oldWaitingJobs = lg.readDataFromTxtFile(queueAnalysisPath)

        # Collect number of waiting time for jobs
        for i in range(len(oldWaitingJobs)):
            currentLine = oldWaitingJobs[i]
            if 'Recommended queue' in currentLine:
                continue
            if 'joeforce' in currentLine or 'joe' in currentLine or 'iw-shared-6' in currentLine:
                queueName, _, _, numberJobWaiting, _ = currentLine.split(' ')
                hashDict[queueName] = int(numberJobWaiting)

        # Get out the best queue has least job waiting
        minimunJob, bestQueue = sys.maxsize, ''
        for queueName in hashDict.keys():
            currentQueueVal = hashDict[queueName]
            if currentQueueVal < minimunJob:
                minimunJob = currentQueueVal
                bestQueue = queueName


        # Get the task/np from the last executed file
        for i in range(len(rawData)):
            currentLine = rawData[i]

            if 'Recommended queue' in currentLine:
                startIndex, endIndex = currentLine.index('[') + 1, currentLine.index(']')
                currentQueueInFile = currentLine[startIndex : endIndex]

            if ('The tasks/np' in rawData[i]):
                previousNumberOfNode = rawData[i]
                break

        # If the best queue from the last recently file not the best queue has the least job waiting time
        '''
            recently:
                iw-shared-6 -> 37 watting
            newest:
                joeforce -> 10 waiting

            -> joeforce must be the one we need to use
        '''

        if currentQueueInFile != bestQueue:
            return False
        else:
            # If the array has value
            if previousNumberOfNode:
                # Get the number of node
                begin, end = previousNumberOfNode.index('[') + 1, previousNumberOfNode.index(']')
                node = previousNumberOfNode[begin: end]

                # Compute the remainNode in server
                remainNode = numberOfCoreLeft(node)

                return remainNode >= nodeRequested
            else:
                return False