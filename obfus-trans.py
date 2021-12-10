#!/usr/bin/env python3
# MIT License Copyright(c) 2021 Hiroshi Shimamoto

import sys

class Line():
    def __init__(self, line):
        self.orig = line
        # parse
        # has indent?
        self.indent = ''
        if line[0] == '\t':
            self.indent = line[0]
        line = line.strip()
        words = line.split()
        first = words[0]
        self.label = ''
        if first[len(first)-1] == ':':
            self.label = first
            if len(words) > 1:
                print("not supported yet")
                exit(1)
        self.directive = ''
        self.opcode = ''
        self.operands = []
        if first[0] == '.':
            # directive?
            if self.label == '':
                self.directive = first
        elif self.label == '':
            self.opcode = first
            self.operands = words[1:]
        self.line = line
        self.words = words
        self.pres = []
        self.posts = []
        self.comment = ''
    def __str__(self):
        line = self.line
        if self.directive == '':
            line = " ".join(self.words)
        if self.comment != '':
            line = f"{line} # {self.comment}"
        return self.indent + line
    def writeto(self, f):
        for line in self.pres:
            line.writeto(f)
        f.write(str(self) + "\n")
        for line in self.posts:
            line.writeto(f)

def parse_lines(ss):
    lines = []
    for s in ss:
        lines.append(Line(s))
    return lines

class Func():
    def __init__(self, name, startline):
        self.name = name
        self.startline = startline
        self.cfi_offset = None
        self.first = None
        self.top = None
        self.frame_start = None
        self.frame_end = None
        self.frame_alloc = None
        self.frame_restore = None
        self.rets = []
        self.lines = []
        self.regs = []
        startline.comment = f"start function {name}"

class Target():
    def __init__(self, src):
        # read source file
        self.src = src
        self.dst = src + ".obfus.s"
    def save(self):
        with open(self.dst, "w") as f:
            for line in self.lines:
                line.writeto(f)

    def analyze(self):
        # read all lines
        with open(self.src, "r") as f:
            self.lines = parse_lines(f.readlines())
        # extract functions
        section = ''
        self.functions = []
        self.ident = None
        currfunc = None
        for line in self.lines:
            if line.directive == '.text':
                section = 'text'
            elif line.directive == '.section':
                section = line.words[1]
            line.section = section
            if line.directive == '.ident':
                self.ident = line
            if line.directive == '.type':
                # .type	main, @function
                typedef = (line.words[1].strip(','), line.words[2])
                print(typedef)
                if typedef[1] == '@function':
                    currfunc = Func(typedef[0], line)
                    self.functions.append(currfunc)
            if line.directive == '.cfi_startproc':
                if currfunc == None:
                    print("detect unknown function")
                    currfunc = Func('', line)
                    self.functions.append(currfunc)
                currfunc.cfi_startproc = line
            if line.directive == '.cfi_offset':
                currfunc.cfi_offset = line

            if currfunc != None:
                line.func = currfunc
                currfunc.lines.append(line)
                if line.opcode != '':
                    if currfunc.first == None:
                        currfunc.first = line
                        print(f"{currfunc.name} {line.opcode}")
                    if currfunc.cfi_offset != None and currfunc.top == None:
                        currfunc.top = line
                if line.opcode == 'ret':
                    currfunc.rets.append(line)

            if line.directive == '.cfi_endproc':
                currfunc.cfi_endproc = line
                currfunc = None

        for f in self.functions:
            # link ops
            prev = None
            for line in f.lines:
                if prev != None:
                    line.prev = prev
                    prev.next = line
                prev = line
            # get all registers using in this function
            regs = []
            for line in f.lines:
                if line.opcode == '':
                    continue
                for r in line.operands:
                    reg = ''
                    for c in r:
                        if c == '%':
                            reg = c
                            continue
                        if c == ',' or c == ')':
                            if reg != '':
                                regs.append(reg)
                            reg = ''
                            continue
                        if reg != '':
                            reg += c
                    if reg != '':
                        regs.append(reg)
            f.regs = list(set(regs))
            print(f.regs)
            # find the frame info
            for line in f.lines:
                if f.frame_start == None:
                    if line.opcode == 'movq':
                        if line.operands[0] == '%rsp,' and line.operands[1] == '%rbp':
                            f.frame_start = line
                if f.frame_end == None:
                    if line.opcode == 'leave':
                        f.frame_end = line
                if f.frame_alloc == None:
                    if line.opcode == 'subq':
                        if line.operands[1] == '%rsp':
                            f.frame_alloc = line
                if f.frame_restore == None:
                    if f.frame_end != None:
                        f.frame_restore = f.frame_end
                    elif line.opcode == 'addq':
                        if line.operands[1] == '%rsp':
                            f.frame_restore = line
            if f.frame_start != None:
                f.frame_start.comment = "frame start"
            if f.frame_end != None:
                f.frame_end.comment = "frame end"
            if f.frame_alloc != None:
                f.frame_alloc.comment = "frame alloc"
            if f.frame_restore != None:
                if f.frame_end == f.frame_restore:
                    f.frame_restore.comment = "frame restore end"
                else:
                    f.frame_restore.comment = "frame restore"

    def obfuscate_simple(self):
        for f in self.functions:
            for line in f.lines:
                op = line.opcode
                if op != 'call':
                    continue
                ss = [
                        "jmp 1f",
                        ".byte 0x48, 0xb8, 0x12, 0x34, 0x56",
                        "1:",
                    ]
                line.pres.extend(parse_lines(ss))

    def obfuscate_indirect_simple(self):
        for f in self.functions:
            p = f.frame_alloc
            if p == None:
                continue
            for line in f.lines:
                if line.opcode != 'call':
                    continue
                ss = [
                        f"push %rax",
                        f"lea {f.name}(%rip), %rax",
                        f"add 1f(%rip), %rax",
                        f"cmp $0, %rax",
                        f"je 2f",
                        f"jmp *%rax",
                        f".data",
                        f"1:",
                        f".quad 3f-{f.name}",
                        f".previous",
                        f"2:",
                        f"pop %rax", # dummy
                        f".byte 0x48, 0xb8, 0x00, 0x00",
                        f"3:",
                        f"pop %rax",
                    ]
                line.pres.extend(parse_lines(ss))

def main():
    if len(sys.argv) != 2:
        exit(1)
    src = sys.argv[1]
    target = Target(src)
    target.analyze()
    target.obfuscate_indirect_simple()
    target.save()

if __name__ == '__main__':
    main()
